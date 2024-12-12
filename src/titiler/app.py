import os
import logging
from fastapi.logger import logger as fastapi_logger

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from titiler.core.factory import TilerFactory
from titiler.core.errors import DEFAULT_STATUS_CODES, add_exception_handlers
from fastapi.responses import JSONResponse

from src.common.routers.check import connectivity, dns, health, sentry_error, logs

from src.titiler.lib.titiler_algorithms import algorithms
from src.titiler.routers.pages import home, map, upload, directory

## LOGGING SETUP ##

gunicorn_error_logger = logging.getLogger("gunicorn.error")
gunicorn_logger = logging.getLogger("gunicorn")
uvicorn_access_logger = logging.getLogger("uvicorn.access")
fastapi_logger = logging.getLogger("fastapi")

# Ensure all loggers use the same handlers
uvicorn_access_logger.handlers = gunicorn_error_logger.handlers
fastapi_logger.handlers = gunicorn_error_logger.handlers

# Set log level
fastapi_logger.setLevel(logging.DEBUG)

# Add a stream handler to capture logs to stdout
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
stream_handler.setFormatter(formatter)

# Add the stream handler to all loggers
gunicorn_error_logger.addHandler(stream_handler)
gunicorn_logger.addHandler(stream_handler)
uvicorn_access_logger.addHandler(stream_handler)
fastapi_logger.addHandler(stream_handler)

## APP SETUP ##
app = FastAPI(docs_url="/documentation")
app.mount("/static", StaticFiles(directory="src/titiler/static"), name="static")
add_exception_handlers(app, DEFAULT_STATUS_CODES)

## CORS / LOCAL DEV ##
if os.getenv("ENV") == "LOCAL" and os.getenv("DEBUG_SERVICE") == "TITILER":
    # Set up debugpy
    import debugpy

    debugpy.listen(("0.0.0.0", 8678))
    print("Waiting for debugger attach...")
    debugpy.wait_for_client()
    print("Debugger attached")

else:
    allowed_origins = [os.getenv("GCP_CLOUD_RUN_ENDPOINT_BURN_BACKEND")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "Accept",
        "Origin",
        "X-Requested-With",
        "Access-Control-Request-Method",
        "Access-Control-Request-Headers",
    ],
    expose_headers=["Access-Control-Allow-Origin", "Access-Control-Allow-Credentials"],
    max_age=3600,
)

### WEB PAGES ###
app.include_router(home.router)
app.include_router(map.router)
app.include_router(upload.router)
app.include_router(directory.router)

### CHECK ###
app.include_router(health.router)
app.include_router(sentry_error.router)
app.include_router(connectivity.router)
app.include_router(dns.router)
app.include_router(logs.router)

### TILESERVER ###
cog = TilerFactory(process_dependency=algorithms.dependency)
app.include_router(cog.router, prefix="/cog", tags=["tileserver"])
