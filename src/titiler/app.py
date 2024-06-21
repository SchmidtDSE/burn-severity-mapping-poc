from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from titiler.core.factory import TilerFactory
from titiler.core.errors import DEFAULT_STATUS_CODES, add_exception_handlers

from src.titiler.lib.titiler_algorithms import algorithms

## APP SETUP ##
app = FastAPI(docs_url="/documentation")
add_exception_handlers(app, DEFAULT_STATUS_CODES)

### TILESERVER ###
cog = TilerFactory(process_dependency=algorithms.dependency)
app.include_router(cog.router, prefix="/cog", tags=["tileserver"])
