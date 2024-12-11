import os
from datetime import datetime

import logging
from fastapi.logger import logger as fastapi_logger

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.common.routers.check import connectivity, dns, health, sentry_error, logs

from src.burn_backend.routers.analyze import spectral_burn_metrics
from src.burn_backend.routers.refine import flood_fill_segmentation
from src.burn_backend.routers.upload import drawn_aoi, shapefile_zip
from src.burn_backend.routers.fetch import rangeland_analysis_platform, ecoclass
from src.burn_backend.routers.list import derived_products
from src.burn_backend.routers.batch import batch_analyze_and_fetch


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

print(os.getenv("ENV"))

## CORS / LOCAL DEV ##
if os.getenv("ENV") == "LOCAL":
    # Set up CORS for local development
    allowed_origins = [os.getenv("LOCAL_ENDPOINT_TITILER", "http://localhost:8081")]

    if os.getenv("DEBUG_SERVICE") == "BURN_BACKEND":
        # Set up debugpy
        import debugpy

        debugpy.listen(("0.0.0.0", 5678))
        print("Waiting for debugger attach...")
        debugpy.wait_for_client()
        print("Debugger attached")

else:
    allowed_origins = [os.getenv("GCP_CLOUD_RUN_ENDPOINT_TITILER")]

app.add_middleware(
    CORSMiddleware,
    # allow_origins=allowed_origins,  # Allows specified origins
    allow_origins=["*"],  # Allows all origins (DEBUG)
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

### CHECK ###
app.include_router(health.router)
app.include_router(sentry_error.router)
app.include_router(connectivity.router)
app.include_router(dns.router)
app.include_router(logs.router)

### ANALYZE ###
app.include_router(spectral_burn_metrics.router)

### REFINE ###
app.include_router(flood_fill_segmentation.router)

### UPLOAD ###
app.include_router(drawn_aoi.router)
app.include_router(shapefile_zip.router)

### FETCH ###
app.include_router(rangeland_analysis_platform.router)
app.include_router(ecoclass.router)

### BATCH ###
app.include_router(batch_analyze_and_fetch.router)

### LIST ###
app.include_router(derived_products.router)
