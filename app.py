import os
import json
from pathlib import Path
import uvicorn
from pydantic import BaseModel
from google.cloud import logging

# For network debugging
import socket
import requests
from fastapi import HTTPException

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from titiler.core.factory import TilerFactory
from titiler.core.errors import DEFAULT_STATUS_CODES, add_exception_handlers

from src.lib.query_sentinel import Sentinel2Client
from src.util.sftp import SFTPClient
from src.util.gcp_secrets import get_ssh_secret
from src.lib.titiler_algorithms import algorithms


# app = Flask(__name__)
app = FastAPI()
cog = TilerFactory(process_dependency=algorithms.dependency)
app.include_router(cog.router, prefix='/cog', tags=["Cloud Optimized GeoTIFF"])
add_exception_handlers(app, DEFAULT_STATUS_CODES)

templates = Jinja2Templates(directory="src/")

logging_client = logging.Client(project='dse-nps')
log_name = "burn-backend"
logger = logging_client.logger(log_name)

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

@app.get("/available-cogs")
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

# # create a POST endpoint for running a burn query with an input geojson, with its associated POST body class
class AnaylzeBurnPOSTBody(BaseModel):
    geojson: dict
    date_ranges: dict
    fire_event_name: str

@app.post("/analyze-burn")
def analyze_burn(body: AnaylzeBurnPOSTBody, sftp_client: SFTPClient = Depends(get_sftp_client)):
    geojson = body.geojson
    date_ranges = body.date_ranges
    fire_event_name = body.fire_event_name
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

@app.get("/map/{fire_event_name}", response_class=HTMLResponse)
def serve_map(request: Request, fire_event_name: str, manifest: dict = Depends(get_manifest)):
    tileserver_endpoint = 'https://tf-rest-burn-severity-ohi6r6qs2a-uc.a.run.app'
    # tileserver_endpoint = 'http://localhost:5050'
    cog_url = f"https://burn-severity-backend.s3.us-east-2.amazonaws.com/public/{fire_event_name}/rbr.tif"
    cog_tileserver_url_prefix = tileserver_endpoint + f"/cog/tiles/WebMercatorQuad/{{z}}/{{x}}/{{y}}.png?url={cog_url}&return_mask=true&nodata=-.9999&algorithm=classify&algorithm_params="

    fire_metadata = manifest[fire_event_name]
    fire_metadata_json = json.dumps(fire_metadata)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "fire_event_name": fire_event_name,
        "fire_metadata_json": fire_metadata_json,
        "cog_tileserver_url_prefix": cog_tileserver_url_prefix
    })