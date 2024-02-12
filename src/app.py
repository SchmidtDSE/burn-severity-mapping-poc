import os
import json
from pathlib import Path
import uvicorn
from pydantic import BaseModel
from google.cloud import logging
import tempfile
from typing import Tuple, List, Any
from pydantic import BaseModel
import pandas as pd
import sentry_sdk
from markdown import markdown
from pathlib import Path
# For network debugging
import requests
from fastapi import HTTPException

from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    Request,
    UploadFile,
    File,
    Form,
    Query,
)
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from src.routers.check import (
    connectivity,
    dns,
    health,
    sentry_error
)
from src.routers.analyze import (
    spectral_burn_metrics
)
from src.routers.upload import (
    drawn_aoi,
    shapefile_zip
)
from src.routers.fetch import (
    rangeland_analysis_platform,
    ecoclass
)
from src.routers.list import (
    derived_products
)

from titiler.core.factory import TilerFactory
from titiler.core.errors import DEFAULT_STATUS_CODES, add_exception_handlers

from src.lib.titiler_algorithms import algorithms

## APP SETUP ##
app = FastAPI(docs_url="/documentation")
add_exception_handlers(app, DEFAULT_STATUS_CODES)
app.mount("/static", StaticFiles(directory="src/static"), name="static")
templates = Jinja2Templates(directory="src/static")

### CHECK ###
app.include_router(health.router)
app.include_router(sentry_error.router)
app.include_router(connectivity.router)
app.include_router(dns.router)

### ANALYZE ###
app.include_router(spectral_burn_metrics.router)

### UPLOAD ### 
app.include_router(drawn_aoi.router)
app.include_router(shapefile_zip.router)

### FETCH ###
app.include_router(rangeland_analysis_platform.router)
app.include_router(ecoclass.router)

### LIST ###
app.include_router(derived_products.router)

### TILESERVER ###
cog = TilerFactory(process_dependency=algorithms.dependency)
app.include_router(cog.router, prefix="/cog", tags=["tileserver"])

### WEB PAGES ###


# @app.get(
#     "/map/{affiliation}/{fire_event_name}/{burn_metric}", response_class=HTMLResponse
# )
# def serve_map(
#     request: Request,
#     fire_event_name: str,
#     burn_metric: str,
#     affiliation: str,
#     manifest: dict = Depends(get_manifest),
# ):
#     mapbox_token = get_mapbox_secret()

#     tileserver_endpoint = os.getenv("GCP_CLOUD_RUN_ENDPOINT")
#     # tileserver_endpoint = "http://localhost:5050"

#     ## TODO [#21]: Use Tofu Output to construct hardocded cog and geojson urls (in case we change s3 bucket name)
#     cog_url = f"https://burn-severity-backend.s3.us-east-2.amazonaws.com/public/{affiliation}/{fire_event_name}/{burn_metric}.tif"
#     burn_boundary_geojson_url = f"https://burn-severity-backend.s3.us-east-2.amazonaws.com/public/{affiliation}/{fire_event_name}/boundary.geojson"
#     ecoclass_geojson_url = f"https://burn-severity-backend.s3.us-east-2.amazonaws.com/public/{affiliation}/{fire_event_name}/ecoclass_dominant_cover.geojson"
#     severity_obs_geojson_url = f"https://burn-severity-backend.s3.us-east-2.amazonaws.com/public/{affiliation}/{fire_event_name}/burn_field_observations.geojson"
#     cog_tileserver_url_prefix = (
#         tileserver_endpoint
#         + f"/cog/tiles/WebMercatorQuad/{{z}}/{{x}}/{{y}}.png?url={cog_url}&nodata=-99&return_mask=true"
#     )

#     rap_cog_annual_url = f"https://burn-severity-backend.s3.us-east-2.amazonaws.com/public/{affiliation}/{fire_event_name}/rangeland_analysis_platform_annual_forb_and_grass.tif"
#     rap_tileserver_annual_url = (
#         tileserver_endpoint
#         + f"/cog/tiles/WebMercatorQuad/{{z}}/{{x}}/{{y}}.png?url={rap_cog_annual_url}&nodata=-99&return_mask=true"
#     )

#     rap_cog_perennial_url = f"https://burn-severity-backend.s3.us-east-2.amazonaws.com/public/{affiliation}/{fire_event_name}/rangeland_analysis_platform_perennial_forb_and_grass.tif"
#     rap_tileserver_perennial_url = (
#         tileserver_endpoint
#         + f"/cog/tiles/WebMercatorQuad/{{z}}/{{x}}/{{y}}.png?url={rap_cog_perennial_url}&nodata=-99&return_mask=true"
#     )

#     rap_cog_shrub_url = f"https://burn-severity-backend.s3.us-east-2.amazonaws.com/public/{affiliation}/{fire_event_name}/rangeland_analysis_platform_shrub.tif"
#     rap_tileserver_shrub_url = (
#         tileserver_endpoint
#         + f"/cog/tiles/WebMercatorQuad/{{z}}/{{x}}/{{y}}.png?url={rap_cog_shrub_url}&nodata=-99&return_mask=true"
#     )

#     rap_cog_tree_url = f"https://burn-severity-backend.s3.us-east-2.amazonaws.com/public/{affiliation}/{fire_event_name}/rangeland_analysis_platform_tree.tif"
#     rap_tileserver_tree_url = (
#         tileserver_endpoint
#         + f"/cog/tiles/WebMercatorQuad/{{z}}/{{x}}/{{y}}.png?url={rap_cog_tree_url}&nodata=-99&return_mask=true"
#     )


#     fire_metadata = manifest[affiliation][fire_event_name]
#     fire_metadata_json = json.dumps(fire_metadata)

#     with open("src/static/map/burn_metric_text.json") as json_file:
#         burn_metric_text = json.load(json_file)

#     return templates.TemplateResponse(
#         "map/map.html",
#         {
#             "request": request,
#             "mapbox_token": mapbox_token,  # for NAIP and Satetllite in V0
#             "fire_event_name": fire_event_name,
#             "burn_metric": burn_metric,
#             "burn_metric_text": burn_metric_text,
#             "fire_metadata_json": fire_metadata_json,
#             "cog_tileserver_url_prefix": cog_tileserver_url_prefix,
#             "burn_boundary_geojson_url": burn_boundary_geojson_url,
#             "ecoclass_geojson_url": ecoclass_geojson_url,
#             "severity_obs_geojson_url": severity_obs_geojson_url,
#             "rap_tileserver_annual_url": rap_tileserver_annual_url,
#             "rap_tileserver_perennial_url": rap_tileserver_perennial_url,
#             "rap_tileserver_shrub_url": rap_tileserver_shrub_url,
#             "rap_tileserver_tree_url": rap_tileserver_tree_url,
#         },
#     )


# @app.get("/upload", response_class=HTMLResponse)
# def upload(request: Request):
#     mapbox_token = get_mapbox_secret()
#     tileserver_endpoint = os.getenv("GCP_CLOUD_RUN_ENDPOINT")

#     return templates.TemplateResponse(
#         "upload/upload.html",
#         {
#             "request": request,
#             "mapbox_token": mapbox_token,  # for NAIP and Satetllite in V0
#             "tileserver_endpoint": tileserver_endpoint,
#         }
#     )

# @app.get("/directory", response_class=HTMLResponse)
# def directory(request: Request, manifest: dict = Depends(get_manifest)):
#     mapbox_token = get_mapbox_secret()
#     manifest_json = json.dumps(manifest)
#     cloud_run_endpoint = os.getenv("GCP_CLOUD_RUN_ENDPOINT")
#     return templates.TemplateResponse(
#         "directory/directory.html",
#         {
#             "request": request,
#             "manifest": manifest_json,
#             "mapbox_token": mapbox_token,
#             "cloud_run_endpoint": cloud_run_endpoint
#         }
#     )

# @app.get("/sketch", response_class=HTMLResponse)
# def sketch(request: Request):
#     return templates.TemplateResponse("sketch/sketch.html", {"request": request})

# @app.get("/", response_class=HTMLResponse)
# def home(request: Request):
#     # Read the markdown file
#     with open(Path("src/static/home/home.md")) as f:
#         md_content = f.read()

#     # Convert markdown to HTML
#     html_content = markdown(md_content)

#     return templates.TemplateResponse(
#         "home/home.html",
#         {
#             "request": request,
#             "content": html_content,
#         },
#     )