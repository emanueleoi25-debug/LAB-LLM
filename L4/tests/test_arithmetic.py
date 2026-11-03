import pytest

from assistente.arithmetic import CalcError, Problem, evaluate


@pytest.mark.parametrize("expr, expected", [
    ("2 + 3 * 4", 14), ("(2 + 3) * 4", 20), ("((1 + 2) * (3 + 4))", 21),
    ("2^3^2", 512), ("2**3**2", 512), ("-2^2", -4), ("2^-1", 0.5),
    ("-7 // 2", -4), ("-7 % 3", 2), ("17 % 5", 2), ("7 / 2", 3.5),
    (".5 + 5.", 5.5), ("  1+1  ", 2), ("+3", 3), ("2--3", 5), ("--5", 5),
    ("0.1 + 0.2", pytest.approx(0.3)),
])
def test_operators_and_precedence(expr, expected):
    assert evaluate(expr) == expected


@pytest.mark.parametrize("alt, ascii_", [
    ("7 × 6", "7 * 6"), ("7 · 6", "7 * 6"), ("8 ÷ 2", "8 / 2"), ("8 : 2", "8 / 2"),
    ("5 − 3", "5 - 3"), ("2 ^ 10", "2 ** 10"),
])
def test_alternative_symbols(alt, ascii_):
    assert evaluate(alt) == evaluate(ascii_)


@pytest.mark.parametrize("expr, problem, char", [
    ("", Problem.EMPTY, None),
    ("   ", Problem.EMPTY, None),
    ("1+" * 100 + "1", Problem.TOO_LONG, None),  # 201 caratteri
    ("3,5 * 2", Problem.COMMA, None),
    ("abs(1,5)", Problem.COMMA, None),  # la virgola si controlla prima delle lettere
    ("abs(1)", Problem.CHARACTER, "a"),
    ("1e5", Problem.CHARACTER, "e"),
    ("0x10", Problem.CHARACTER, "x"),
    ("1_000", Problem.CHARACTER, "_"),
    ("__import__('os')", Problem.CHARACTER, "_"),
    ("3 x 4", Problem.CHARACTER, "x"),
    ("1234 * 5678 =", Problem.CHARACTER, "="),
    ("2²", Problem.CHARACTER, "²"),
    ("٣ + 1", Problem.CHARACTER, "٣"),
    ("2 3", Problem.SYNTAX, None),
    ("3 +", Problem.SYNTAX, None),
    ("2****3", Problem.SYNTAX, None),
    ("()", Problem.SYNTAX, None),
    ("2(3+4)", Problem.SYNTAX, None),
    ("(1)(2)", Problem.SYNTAX, None),
    ("1 000 + 1", Problem.SYNTAX, None),
    ("1/0 + 2(3)", Problem.SYNTAX, None),  # la sintassi si controlla prima del calcolo
    ("1000000000000001", Problem.NUMBER_RANGE, None),
    ("0.0000000000000001", Problem.NUMBER_RANGE, None),
    ("1 / 0", Problem.DIVISION_BY_ZERO, None),
    ("1 // 0", Problem.DIVISION_BY_ZERO, None),
    ("1 % 0", Problem.DIVISION_BY_ZERO, None),
    ("0^-1", Problem.DIVISION_BY_ZERO, None),
    ("(-8)^0.5", Problem.NOT_REAL, None),
    ("9^9^9", Problem.TOO_BIG, None),
    ("(10^8)^2 / 10^10", Problem.TOO_BIG, None),
    ("1000000000000000 + 1", Problem.TOO_BIG, None),
    ("0.5^10000", Problem.TOO_SMALL, None),
    ("0.000000000000001 / 10", Problem.TOO_SMALL, None),
])
def test_problems(expr, problem, char):
    with pytest.raises(CalcError) as info:
        evaluate(expr)
    assert info.value.problem is problem
    assert info.value.char == char


def test_limits_are_inclusive():
    assert evaluate("1000000000000000") == 1e15
    assert evaluate("0.000000000000001") == 1e-15
    assert evaluate("0") == 0
    assert evaluate("1+" * 99 + "11") == 110  # esattamente 200 caratteri: accettata


def test_negative_base_with_integer_exponent():
    assert evaluate("(-2)^3") == -8


@pytest.mark.parametrize("expr, expected", [
    ("0.1 + 0.2 - 0.3", 0),
    ("1.1 - 1 - 0.1", 0),
    ("3 * 0.1 - 0.3", 0),
    ("100 * 1.1 - 110", 0),
    ("0.1 + 0.2", 0.3),  # uguaglianza esatta, non approx
    ("1000000000000000 - 1", 999999999999999),
    ("999999999999999.5 - 0.5", 999999999999999),
])
def test_addition_noise_is_rounded(expr, expected):
    assert evaluate(expr) == expected
