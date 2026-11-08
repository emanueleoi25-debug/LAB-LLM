"""App FastAPI del servizio catalogo: strato sottile sopra `inventario`.

L'inventario si legge una volta all'avvio. Gli errori dovuti ai dati dell'utente diventano
risposte 400 con `{"detail": ...}`; un codice inesistente diventa una risposta 404.
"""

from dataclasses import asdict

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from servizio_catalogo import inventario
from servizio_catalogo.inventario import CatalogError

ITEMS = inventario.load_items()  # se il file non è valido il servizio non parte

app = FastAPI(title="Servizio catalogo del laboratorio")


@app.exception_handler(CatalogError)
def catalog_error_handler(request: Request, exc: CatalogError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(RequestValidationError)
def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    name = exc.errors()[0]["loc"][-1]
    return JSONResponse(
        status_code=400, content={"detail": f"parametro '{name}' mancante o non valido."}
    )


@app.get("/cerca")
def cerca(q: str, categoria: str | None = None) -> dict:
    result = inventario.search(ITEMS, q, categoria)
    return {
        "query": q.strip(),
        "categoria": result.category,
        "totale": result.total,
        "articoli": [
            {
                "codice": item.codice,
                "nome": item.nome,
                "posizione": item.posizione,
                "quantita": item.quantita,
                "stato": item.stato,
            }
            for item in result.items
        ],
    }


@app.get("/articolo", response_model=None)
def articolo(codice: str) -> dict | JSONResponse:
    item = inventario.find(ITEMS, codice)
    if item is None:
        return JSONResponse(
            status_code=404,
            content={"detail": f"nessun articolo con codice '{codice.strip().upper()}'."},
        )
    return asdict(item)


@app.get("/salute")
def salute() -> dict:
    return {"stato": "ok", "articoli": len(ITEMS)}
