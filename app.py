import os
import json
from pathlib import Path
import uvicorn
from pydantic import BaseModel
from google.cloud import logging
import tempfile

# For network debugging
import socket
import requests
from fastapi import HTTPException

from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    Request,
    UploadFile,
    File,
    Form
)
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from titiler.core.factory import TilerFactory
from titiler.core.errors import DEFAULT_STATUS_CODES, add_exception_handlers

from src.lib.query_sentinel import Sentinel2Client
from src.util.sftp import SFTPClient
from src.util.gcp_secrets import get_ssh_secret, get_mapbox_secret
from src.util.ingest_burn_zip import ingest_esri_zip_file, shp_to_geojson
from src.lib.titiler_algorithms import algorithms
from src.lib.query_soil import sdm_create_aoi, sdm_get_available_interpretations, sdm_get_esa_mapunitid_poly
# app = Flask(__name__)
app = FastAPI()
cog = TilerFactory(process_dependency=algorithms.dependency)
app.include_router(cog.router, prefix='/cog', tags=["Cloud Optimized GeoTIFF"])
add_exception_handlers(app, DEFAULT_STATUS_CODES)


logging_client = logging.Client(project='dse-nps')
log_name = "burn-backend"
logger = logging_client.logger(log_name)

app.mount("/static", StaticFiles(directory="src/static"), name="static")
templates = Jinja2Templates(directory="src/static")

### HELPERS ###

@app.get("/")
def index():
    logger.log_text("ping pong")
    return "Alive", 200

@app.get("/check-connectivity")
def check_connectivity():
    try:
        response = requests.get("http://example.com")
        logger.log_text(f"Connectivity check: Got response {response.status_code} from http://example.com")
        return {"status_code": response.status_code, "response_body": response.text}
    except Exception as e:
        logger.log_text(f"Connectivity check: Error {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/check-dns")
def check_dns():
    try:
        SFTP_SERVER_ENDPOINT = os.getenv('SFTP_SERVER_ENDPOINT')
        ip_address = socket.gethostbyname(SFTP_SERVER_ENDPOINT)
        logger.log_text(f"DNS check: Resolved {SFTP_SERVER_ENDPOINT} to {ip_address}")
        return {"ip_address": ip_address}
    except Exception as e:
        logger.log_text(f"DNS check: Error {e}")
        raise HTTPException(status_code=500, detail=str(e))

### DEPENDENCIES ###

def get_sftp_client():
    SFTP_SERVER_ENDPOINT = os.getenv('SFTP_SERVER_ENDPOINT')
    SFTP_ADMIN_USERNAME = os.getenv('SFTP_ADMIN_USERNAME')
    SSH_SECRET = get_ssh_secret()

    logger.log_text(f"SFTP_SERVER_ENDPOINT: {SFTP_SERVER_ENDPOINT}")
    logger.log_text(f"SFTP_ADMIN_USERNAME: {SFTP_ADMIN_USERNAME}")
    logger.log_text(f"SSH_SECRET (trunc): {SSH_SECRET[:20]}")

    return SFTPClient(SFTP_SERVER_ENDPOINT, SFTP_ADMIN_USERNAME, SSH_SECRET)

def get_manifest(sfpt_client: SFTPClient = Depends(get_sftp_client)):
    try:
        sfpt_client.connect()
        manifest = sfpt_client.get_manifest()
        sfpt_client.disconnect()
        return manifest
    except Exception as e:
        logger.log_text(f"Error: {e}")
        return f"Error: {e}", 400

### API ENDPOINTS ###

@app.get("/api/available-cogs")
def available_cogs(sftp_client: SFTPClient = Depends(get_sftp_client)):
    try:
        sftp_client.update_available_cogs()

        response = {
            "message": "updated available cogs",
            "available_cogs": sftp_client.available_cogs
        }
        logger.log_text(f"Available COGs updated: {sftp_client.available_cogs}")
        return response, 200
    except Exception as e:
        logger.log_text(f"Error: {e}")
        return f"Error: {e}", 400

class AnaylzeBurnPOSTBody(BaseModel):
    geojson: str
    date_ranges: dict
    fire_event_name: str
    affiliation: str

@app.post("/api/analyze-burn")
def analyze_burn(body: AnaylzeBurnPOSTBody, sftp_client: SFTPClient = Depends(get_sftp_client)):
    geojson = json.loads(body.geojson)
    # geojson = body.geojson

    date_ranges = body.date_ranges
    fire_event_name = body.fire_event_name
    affiliation = body.affiliation  
    logger.log_text(f"Received analyze-burn request for {fire_event_name}")

    try:
        # create a Sentinel2Client instance
        geo_client = Sentinel2Client(geojson_bounds=geojson, buffer=0.1)

        # get imagery data before and after the fire
        geo_client.query_fire_event(
            prefire_date_range=date_ranges["prefire"],
            postfire_date_range=date_ranges["postfire"],
            from_bbox=True,
        )
        logger.log_text(f"Obtained imagery for {fire_event_name}")

        # calculate burn metrics
        geo_client.calc_burn_metrics()
        logger.log_text(f"Calculated burn metrics for {fire_event_name}")

        # save the cog to the FTP server
        sftp_client.connect()
        sftp_client.upload_fire_event(
            metrics_stack=geo_client.metrics_stack,
            affiliation=affiliation,
            fire_event_name=fire_event_name,
            prefire_date_range=date_ranges["prefire"],
            postfire_date_range=date_ranges["postfire"]
        )
        sftp_client.disconnect()
        logger.log_text(f"Cogs uploaded for {fire_event_name}")
        
        return f"cog uploadeds for {fire_event_name}", 200

    except Exception as e:
        logger.log_text(f"Error: {e}")
        return f"Error: {e}", 400


class QuerySoilPOSTBody(BaseModel):
    geojson: dict
    fire_event_name: str

# @app.post("/api/query-soil/create-aoi")
# def create_aoi(body: QuerySoilPOSTBody, sftp_client: SFTPClient = Depends(get_sftp_client)):
#     # geojson = json.loads(body.geojson)
#     geojson = body.geojson
#     fire_event_name = body.fire_event_name
#     aoi_response = sdm_create_aoi(geojson)
#     aoi_smd_id = aoi_response.json()['id']
#     return JSONResponse(status_code=200, content={"aoi_smd_id": aoi_smd_id})

# @app.get("/api/query-soil/get-available-interpretations")
# def get_sdm_interpretations(aoi_smd_id: str):
#     available_interpretations = sdm_get_available_interpretations(aoi_smd_id)
#     return JSONResponse(status_code=200, content={"available_interpretations": available_interpretations})

@app.post('/api/query-soil/get-esa-mapunitid-poly')
def get_esa_mapunitid_poly(body: QuerySoilPOSTBody):
    geojson = body.geojson
    fire_event_name = body.fire_event_name
    mapunitpoly_geojson = sdm_get_esa_mapunitid_poly(geojson)
    return JSONResponse(status_code=200, content={"mapunitpoly_geojson": json.loads(mapunitpoly_geojson)})
    # return polygon_response

@app.post("/api/upload-shapefile-zip")
async def upload_shapefile(fire_event_name: str = Form(...), affiliation: str = Form(...), file: UploadFile = File(...), sftp_client: SFTPClient = Depends(get_sftp_client)):
    try:
        # Read the file
        zip_content = await file.read()

        # Write the content to a temporary file
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            tmp.write(zip_content)
            tmp_zip = tmp.name

        valid_shp, valid_tiff = ingest_esri_zip_file(tmp_zip)

        # For now assert that there is only one shapefile
        assert len(valid_shp) == 1, "Zip must contain exactly one shapefile (with associated files: .shx, .prj and optionally, .dbf)" 
        __shp_paths, geojson = valid_shp[0] 

        # Upload the zip and a geojson to SFTP
        sftp_client.connect()

        sftp_client.upload(
            source_local_path=tmp_zip,
            remote_path=f"{affiliation}/{fire_event_name}/user_uploaded_{file.filename}"
        )

        with tempfile.NamedTemporaryFile(suffix=".geojson", delete=False) as tmp:
            tmp_geojson = tmp.name
            with open(tmp_geojson, "w") as f:
                f.write(geojson)
            sftp_client.upload(
                source_local_path=tmp_geojson,
                remote_path=f"{affiliation}/{fire_event_name}/boundary.geojson"
            )

        sftp_client.disconnect()


        return JSONResponse(status_code=200, content={"geojson": geojson})

    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

### WEB PAGES ###

@app.get("/map/{affiliation}/{fire_event_name}/{burn_metric}", response_class=HTMLResponse)
def serve_map(request: Request, fire_event_name: str, burn_metric: str, affiliation: str, manifest: dict = Depends(get_manifest)):
    mapbox_token = get_mapbox_secret()

    tileserver_endpoint = 'https://tf-rest-burn-severity-ohi6r6qs2a-uc.a.run.app'
    # tileserver_endpoint = 'http://localhost:5050'
    cog_url = f"https://burn-severity-backend.s3.us-east-2.amazonaws.com/public/{affiliation}/{fire_event_name}/{burn_metric}.tif"
    cog_tileserver_url_prefix = tileserver_endpoint + f"/cog/tiles/WebMercatorQuad/{{z}}/{{x}}/{{y}}.png?url={cog_url}&nodata=-99&return_mask=true"

    fire_metadata = manifest[fire_event_name]
    fire_metadata_json = json.dumps(fire_metadata)

    with open('src/static/burn_metric_text.json') as json_file:
        burn_metric_text = json.load(json_file)

    return templates.TemplateResponse("map.html", {
        "request": request,
        "mapbox_token": mapbox_token, # for NAIP and Satetllite in V0
        "fire_event_name": fire_event_name,
        "burn_metric": burn_metric,
        "burn_metric_text": burn_metric_text,
        "fire_metadata_json": fire_metadata_json,
        "cog_tileserver_url_prefix": cog_tileserver_url_prefix
    })

@app.get("/upload", response_class=HTMLResponse)
def upload(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})
