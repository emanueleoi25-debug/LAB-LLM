"""Analisi e calcolo sicuro di espressioni aritmetiche, senza `eval`.

`ast.parse` costruisce soltanto l'albero sintattico; il calcolo lo fa `_compute`, che conosce solo
numeri, operatori consentiti e segno. Qui non ci sono testi per il modello: gli errori sono
`CalcError` con un `Problem`, tradotto in testo da `tools.py`.
"""

import ast
import operator
import re
from decimal import Decimal
from enum import Enum, auto

MAX_LENGTH = 200
# Intervallo gestito per numeri e risultati diversi da zero (in valore assoluto), come nel
# convertitore: dentro l'intervallo i numeri si scrivono in poche cifre senza notazione scientifica.
MIN_ABS = 1e-15
MAX_ABS = 1e15

_ALTERNATIVES = {"×": "*", "·": "*", "÷": "/", ":": "/", "−": "-", "^": "**"}
# Insieme esplicito: `str.isdigit()` accetterebbe anche `²` o le cifre arabo-indiane.
_ALLOWED_CHARS = frozenset("0123456789.+-*/%() ")
# Zeri iniziali della parte intera (`05` → `5`), che il parser di Python rifiuta; `0.05` resta.
_LEADING_ZEROS = re.compile(r"(?<![\d.])0+(?=\d)")

_BINARY = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_DIVISIONS = (ast.Div, ast.FloorDiv, ast.Mod)
_SUMS = (ast.Add, ast.Sub)


class Problem(Enum):
    EMPTY = auto()
    TOO_LONG = auto()
    COMMA = auto()
    CHARACTER = auto()
    SYNTAX = auto()
    NUMBER_RANGE = auto()
    DIVISION_BY_ZERO = auto()
    NOT_REAL = auto()
    TOO_BIG = auto()
    TOO_SMALL = auto()


class CalcError(Exception):
    """Espressione che non si può calcolare; `char` solo per `Problem.CHARACTER`."""

    def __init__(self, problem: Problem, char: str | None = None) -> None:
        super().__init__(problem.name if char is None else f"{problem.name} {char!r}")
        self.problem = problem
        self.char = char


def _is_allowed(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant):
        return type(node.value) in (int, float)  # esclude bool, complex, stringhe
    if isinstance(node, ast.BinOp):
        return type(node.op) in _BINARY
    if isinstance(node, ast.UnaryOp):
        return type(node.op) in _UNARY
    return isinstance(node, ast.Expression) or isinstance(node, ast.operator | ast.unaryop)


def _parse(text: str) -> ast.Expression:
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError:
        raise CalcError(Problem.SYNTAX) from None
    if not all(_is_allowed(node) for node in ast.walk(tree)):
        raise CalcError(Problem.SYNTAX)
    return tree


def _check_range(value: float, problem_small: Problem, problem_big: Problem) -> float:
    if abs(value) > MAX_ABS:
        raise CalcError(problem_big)
    if value != 0 and abs(value) < MIN_ABS:
        raise CalcError(problem_small)
    return value


def _power(base: float, exponent: float) -> float:
    if base == 0 and exponent < 0:
        raise CalcError(Problem.DIVISION_BY_ZERO)
    if base < 0 and not exponent.is_integer():
        raise CalcError(Problem.NOT_REAL)
    try:
        result = base**exponent
    except OverflowError:
        raise CalcError(Problem.TOO_BIG) from None
    if base != 0 and result == 0:  # sotto il minimo dei float: arrotondato a 0
        raise CalcError(Problem.TOO_SMALL)
    return result


def _round_sum(left: float, right: float, result: float) -> float:
    """Toglie il rumore dei float oltre la 15ª cifra significativa dell'operando più grande.

    `0.1 + 0.2` vale 0.30000000000000004: senza arrotondare, `0.1 + 0.2 - 0.3` darebbe 5.55e-17.
    Due interi (entro 1e15) si sommano esattamente e restano intatti. L'esponente si prende da
    `Decimal`, perché `math.log10` vicino a 1e15 arrotonda per eccesso.
    """
    if left.is_integer() and right.is_integer():
        return result
    exponent = Decimal(max(abs(left), abs(right))).adjusted()
    return round(result, 14 - exponent)


def _compute(node: ast.AST) -> float:
    if isinstance(node, ast.Constant):
        return _check_range(float(node.value), Problem.NUMBER_RANGE, Problem.NUMBER_RANGE)
    if isinstance(node, ast.UnaryOp):
        return _UNARY[type(node.op)](_compute(node.operand))
    left, right = _compute(node.left), _compute(node.right)
    if isinstance(node.op, ast.Pow):
        result = _power(left, right)
    elif isinstance(node.op, _DIVISIONS) and right == 0:
        raise CalcError(Problem.DIVISION_BY_ZERO)
    else:
        result = _BINARY[type(node.op)](left, right)
    if isinstance(node.op, _SUMS):
        result = _round_sum(left, right, result)
    return _check_range(result, Problem.TOO_SMALL, Problem.TOO_BIG)


def evaluate(expression: str) -> float:
    """Valore dell'espressione, sempre 0 o dentro l'intervallo gestito; `CalcError` se non si può."""
    text = expression.strip()
    if not text:
        raise CalcError(Problem.EMPTY)
    if len(text) > MAX_LENGTH:
        raise CalcError(Problem.TOO_LONG)
    if "," in text:
        raise CalcError(Problem.COMMA)
    text = "".join(" " if char.isspace() else char for char in text)
    for alternative, symbol in _ALTERNATIVES.items():
        # Con gli spazi due simboli consecutivi non si fondono: `6::4` non diventa `6//4`.
        text = text.replace(alternative, f" {symbol} ")
    for char in text:
        if char not in _ALLOWED_CHARS:
            raise CalcError(Problem.CHARACTER, char)
    text = _LEADING_ZEROS.sub("", text)
    return _compute(_parse(text).body)
