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
    Form,
    Query
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
from src.lib.query_soil import sdm_get_ecoclassid_from_mu_info, sdm_get_esa_mapunitid_poly, edit_get_ecoclass_info
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

@app.get("/api/query-satellite/available-cogs")
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
    geojson: Any
    date_ranges: dict
    fire_event_name: str
    affiliation: str

# TODO [$65aeac7d58a56800081ec5a4]: Decide on / implement cloud tasks or other async batch
# This is a long running process, and users probably don't mind getting an email notification
# or something similar when the process is complete. Esp if the frontend remanins static. 
@app.post("/api/query-satellite/analyze-burn")
def analyze_burn(body: AnaylzeBurnPOSTBody, sftp_client: SFTPClient = Depends(get_sftp_client)):
    geojson = json.loads(body.geojson)

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
    geojson: Any
    fire_event_name: str
    affiliation: str

@app.post('/api/query-soil/get-esa-mapunitid-poly')
def get_esa_mapunitid_poly(body: QuerySoilPOSTBody):
    geojson = body.geojson
    fire_event_name = body.fire_event_name
    mapunitpoly_geojson = sdm_get_esa_mapunitid_poly(geojson)
    return JSONResponse(status_code=200, content={"mapunitpoly_geojson": json.loads(mapunitpoly_geojson)})
    # return polygon_response

class MUPair(BaseModel):
    mu_pair: Tuple[str, str]

class QueryEcoclassidPOSTBody(BaseModel):
    mu_pair_tuples: List[MUPair]

@app.post('/api/query-soil/get-ecoclassid-from-mu-info')
def get_ecoclassid_from_mu_info(body: QueryEcoclassidPOSTBody):
    mu_pair_tuples = body.mu_pair_tuples
    mrla = sdm_get_ecoclassid_from_mu_info(mu_pair_tuples)
    return JSONResponse(status_code=200, content={"mrla": json.loads(mrla)})

@app.get("/api/query-soil/get-ecoclass-info")
def get_ecoclass_info(ecoclassid: str = Query(...)):
    status_code, ecoclass_info = edit_get_ecoclass_info(ecoclassid)
    return JSONResponse(status_code=status_code, content={"ecoclass_info": ecoclass_info})

# TODO [$65aeac7d58a56800081ec5a5]: Restrucutre FastAPI endpoints to seperate user-facing endpoints from internal endpoints
# refactor out the low level endpoints (/api) and rename others (this isn't really an `analysis` but it does compose a lot of logic like `analyze-burn`)
@app.post("/api/query-soil/analyze-ecoclass") 
def analyze_ecoclass(body: QuerySoilPOSTBody, sftp_client: SFTPClient = Depends(get_sftp_client)):
    fire_event_name = body.fire_event_name
    geojson = json.loads(body.geojson)
    affiliation = body.affiliation

    try:
        mapunit_gdf = sdm_get_esa_mapunitid_poly(geojson)
        mu_polygon_keys = [mupolygonkey for __musym, __nationalmusym, __mukey, mupolygonkey in  mapunit_gdf.index]
        mrla_df = sdm_get_ecoclassid_from_mu_info(mu_polygon_keys)

        # join mapunitids with link table for ecoclassids
        mapunit_with_ecoclassid_df = mapunit_gdf.join(mrla_df).set_index('ecoclassid')

        edit_ecoclass_df_row_dicts = []
        ecoclass_ids = mrla_df['ecoclassid'].unique()

        n_ecoclasses = len(ecoclass_ids)
        n_within_edit = 0

        for ecoclass_id in ecoclass_ids:
            edit_success, edit_ecoclass_json = edit_get_ecoclass_info(ecoclass_id)
            if edit_success:
                n_within_edit += 1
                logger.log_text(f"Success: {ecoclass_id} exists within EDIT backend")
                edit_ecoclass_df_row_dict = edit_ecoclass_json['generalInformation']['dominantSpecies']
                edit_ecoclass_df_row_dict['ecoclassid'] = ecoclass_id
                edit_ecoclass_df_row_dicts.append(edit_ecoclass_df_row_dict)
            else:
                logger.log_text(f"Missing: {edit_ecoclass_json} doesn't exist within EDIT backend")

        logger.log_text(f"Found {n_within_edit} of {n_ecoclasses} ecoclasses ({100*round(n_within_edit/n_ecoclasses, 2)}%) within EDIT backend")

        if n_within_edit > 0:
            edit_ecoclass_df = pd.DataFrame(edit_ecoclass_df_row_dicts).set_index('ecoclassid')
        else:
            # Populate with empty dataframe, for consistency's sake (so that the frontend doesn't have to handle this case)
            edit_ecoclass_df = pd.DataFrame([], columns=
                ['dominantTree1', 'dominantShrub1', 'dominantHerb1', 'dominantTree2','dominantShrub2', 'dominantHerb2']
            )

        # join ecoclassids with edit ecoclass info, to get spatial ecoclass info
        edit_ecoclass_geojson = mapunit_with_ecoclassid_df.join(edit_ecoclass_df, how='left').to_json()

        # save the ecoclass_geojson to the FTP server
        with tempfile.NamedTemporaryFile(suffix=".geojson", delete=False) as tmp:
            tmp_geojson_path = tmp.name
            with open(tmp_geojson_path, "w") as f:
                f.write(edit_ecoclass_geojson)
            sftp_client.connect()
            sftp_client.upload(
                source_local_path=tmp_geojson_path,
                remote_path=f"{affiliation}/{fire_event_name}/ecoclass_dominant_cover.geojson"
            )
            sftp_client.disconnect()

        logger.log_text(f"Ecoclass GeoJSON uploaded for {fire_event_name}")
        return f"Ecoclass GeoJSON uploaded for {fire_event_name}", 200

    except Exception as e:
        logger.log_text(f"Error: {e}")
        return f"Error: {e}", 400

@app.post("/api/upload-shapefile-zip")
async def upload_shapefile(fire_event_name: str = Form(...), affiliation: str = Form(...), file: UploadFile = File(...), sftp_client: SFTPClient = Depends(get_sftp_client)):
    try:
        # Read the file
        zip_content = await file.read()

        # Write the content to a temporary file
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            tmp.write(zip_content)
            tmp_zip = tmp.name

        valid_shp, __valid_tiff = ingest_esri_zip_file(tmp_zip)

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
    burn_boundary_geojson_url =  f"https://burn-severity-backend.s3.us-east-2.amazonaws.com/public/{affiliation}/{fire_event_name}/boundary.geojson"
    ecoclass_geojson_url = f"https://burn-severity-backend.s3.us-east-2.amazonaws.com/public/{affiliation}/{fire_event_name}/ecoclass_dominant_cover.geojson"

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
        "cog_tileserver_url_prefix": cog_tileserver_url_prefix,
        "burn_boundary_geojson_url": burn_boundary_geojson_url,
        "ecoclass_geojson_url": ecoclass_geojson_url
    })

@app.get("/upload", response_class=HTMLResponse)
def upload(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})
