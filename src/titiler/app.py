from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from titiler.core.factory import TilerFactory
from titiler.core.errors import DEFAULT_STATUS_CODES, add_exception_handlers

from src.titiler.lib.titiler_algorithms import algorithms
from src.titiler.routers.pages import home, map, upload, directory

## APP SETUP ##
app = FastAPI(docs_url="/documentation")
add_exception_handlers(app, DEFAULT_STATUS_CODES)

### WEB PAGES ###
app.include_router(home.router)
app.include_router(map.router)
app.include_router(upload.router)
app.include_router(directory.router)

### TILESERVER ###
cog = TilerFactory(process_dependency=algorithms.dependency)
app.include_router(cog.router, prefix="/cog", tags=["tileserver"])

### HEALTHCHECK ###
@app.get("/healthz", tags=["healthcheck"])
def ping():
    """Health check."""
    return {"ping": "pong!"}