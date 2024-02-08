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
    Query,
)
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from titiler.core.factory import TilerFactory
from titiler.core.errors import DEFAULT_STATUS_CODES, add_exception_handlers

from src.lib.query_sentinel import Sentinel2Client
from src.util.cloud_static_io import CloudStaticIOClient
from src.util.gcp_secrets import get_mapbox_secret
from src.util.ingest_burn_zip import ingest_esri_zip_file
from src.lib.titiler_algorithms import algorithms
from src.lib.query_soil import (
    sdm_get_ecoclassid_from_mu_info,
    sdm_get_esa_mapunitid_poly,
    edit_get_ecoclass_info,
)
from src.lib.query_rap import rap_get_biomass

sentry_sdk.init(
    dsn="https://3660129e232b3c796208a5e46945d838@o4506701219364864.ingest.sentry.io/4506701221199872",
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for performance monitoring.
    traces_sample_rate=1.0,
    # Set profiles_sample_rate to 1.0 to profile 100%
    # of sampled transactions.
    # We recommend adjusting this value in production.
    profiles_sample_rate=1.0,
)

app = FastAPI()
cog = TilerFactory(process_dependency=algorithms.dependency)
app.include_router(cog.router, prefix="/cog", tags=["Cloud Optimized GeoTIFF"])
add_exception_handlers(app, DEFAULT_STATUS_CODES)


logging_client = logging.Client(project="dse-nps")
log_name = "burn-backend"
logger = logging_client.logger(log_name)

app.mount("/static", StaticFiles(directory="src/static"), name="static")
templates = Jinja2Templates(directory="src/static")

### HELPERS ###


@app.get("/")
def index():
    logger.log_text("ping pong")
    return "Alive", 200

@app.get("/sentry-debug")
async def trigger_error():
    __division_by_zero = 1 / 0

@app.get("/check-connectivity")
def check_connectivity():
    try:
        response = requests.get("http://example.com")
        logger.log_text(
            f"Connectivity check: Got response {response.status_code} from http://example.com"
        )
        return {"status_code": response.status_code, "response_body": response.text}
    except Exception as e:
        logger.log_text(f"Connectivity check: Error {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/check-dns")
def check_dns():
    try:
        SFTP_SERVER_ENDPOINT = os.getenv("SFTP_SERVER_ENDPOINT")
        ip_address = socket.gethostbyname(SFTP_SERVER_ENDPOINT)
        logger.log_text(f"DNS check: Resolved {SFTP_SERVER_ENDPOINT} to {ip_address}")
        return {"ip_address": ip_address}
    except Exception as e:
        logger.log_text(f"DNS check: Error {e}")
        raise HTTPException(status_code=400, detail=str(e))


### DEPENDENCIES ###

def get_cloud_static_io_client():
    return CloudStaticIOClient('burn-severity-backend', "s3")

def get_manifest(cloud_static_io_client: CloudStaticIOClient = Depends(get_cloud_static_io_client)):
    manifest = cloud_static_io_client.get_manifest()
    return manifest

def init_sentry():
    sentry_sdk.init(
        dsn="https://3660129e232b3c796208a5e46945d838@o4506701219364864.ingest.sentry.io/4506701221199872",
        # Set traces_sample_rate to 1.0 to capture 100%
        # of transactions for performance monitoring.
        traces_sample_rate=1.0,
        # Set profiles_sample_rate to 1.0 to profile 100%
        # of sampled transactions.
        # We recommend adjusting this value in production.
        profiles_sample_rate=1.0,
    )
    sentry_sdk.set_context("env", {"env": os.getenv('ENV')})
    logger.log_text("Sentry initialized")


### API ENDPOINTS ###

class AnaylzeBurnPOSTBody(BaseModel):
    geojson: Any
    derive_boundary: bool
    date_ranges: dict
    fire_event_name: str
    affiliation: str


# TODO [#5]: Decide on / implement cloud tasks or other async batch
# This is a long running process, and users probably don't mind getting an email notification
# or something similar when the process is complete. Esp if the frontend remanins static.
@app.post("/api/query-satellite/analyze-burn")
def analyze_burn(
    body: AnaylzeBurnPOSTBody, cloud_static_io_client: CloudStaticIOClient = Depends(get_cloud_static_io_client), __sentry = Depends(init_sentry)
):
    geojson_boundary = json.loads(body.geojson)

    date_ranges = body.date_ranges
    fire_event_name = body.fire_event_name
    affiliation = body.affiliation
    derive_boundary = body.derive_boundary
    derived_boundary = None

    sentry_sdk.set_context("analyze_burn", {"request": body})
    logger.log_text(f"Received analyze-burn request for {fire_event_name}")

    try:
        # create a Sentinel2Client instance
        geo_client = Sentinel2Client(geojson_boundary=geojson_boundary, buffer=0.1)

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

        if derive_boundary:
            # Derive a boundary from the imagery
            # TODO [#16]: Derived boundary hardcoded for rbr / .025 threshold
            # Not sure yet but we will probably want to make this configurable
            geo_client.derive_boundary("rbr", 0.025)
            logger.log_text(f"Derived boundary for {fire_event_name}")

            # Upload the derived boundary

            with tempfile.NamedTemporaryFile(suffix=".geojson", delete=False) as tmp:
                tmp_geojson = tmp.name
                with open(tmp_geojson, "w") as f:
                    f.write(geo_client.geojson_boundary.to_json())

                cloud_static_io_client.upload(
                    source_local_path=tmp_geojson,
                    remote_path=f"public/{affiliation}/{fire_event_name}/boundary.geojson",
                )

            # Return the derived boundary
            derived_boundary = geo_client.geojson_boundary.to_json()

        # save the cog to the FTP server
        cloud_static_io_client.upload_fire_event(
            metrics_stack=geo_client.metrics_stack,
            affiliation=affiliation,
            fire_event_name=fire_event_name,
            prefire_date_range=date_ranges["prefire"],
            postfire_date_range=date_ranges["postfire"],
            derive_boundary=derive_boundary,
        )
        logger.log_text(f"Cogs uploaded for {fire_event_name}")

        return JSONResponse(
            status_code=200,
            content={
                "message": f"Cogs uploaded for {fire_event_name}",
                "fire_event_name": fire_event_name,
                "derived_boundary": derived_boundary,
            },
        )
    
    except Exception as e:
        sentry_sdk.capture_exception(e)
        logger.log_text(f"Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

class QuerySoilPOSTBody(BaseModel):
    geojson: Any
    fire_event_name: str
    affiliation: str


@app.post("/api/query-soil/get-esa-mapunitid-poly")
def get_esa_mapunitid_poly(body: QuerySoilPOSTBody):
    geojson = body.geojson
    fire_event_name = body.fire_event_name
    mapunitpoly_geojson = sdm_get_esa_mapunitid_poly(geojson)
    return JSONResponse(
        status_code=200,
        content={"mapunitpoly_geojson": json.loads(mapunitpoly_geojson)},
    )
    # return polygon_response


class MUPair(BaseModel):
    mu_pair: Tuple[str, str]


class QueryEcoclassidPOSTBody(BaseModel):
    mu_pair_tuples: List[MUPair]


@app.post("/api/query-soil/get-ecoclassid-from-mu-info")
def get_ecoclassid_from_mu_info(body: QueryEcoclassidPOSTBody):
    mu_pair_tuples = body.mu_pair_tuples
    mrla = sdm_get_ecoclassid_from_mu_info(mu_pair_tuples)
    return JSONResponse(status_code=200, content={"mrla": json.loads(mrla)})


@app.get("/api/query-soil/get-ecoclass-info")
def get_ecoclass_info(ecoclassid: str = Query(...)):
    status_code, ecoclass_info = edit_get_ecoclass_info(ecoclassid)
    return JSONResponse(
        status_code=status_code, content={"ecoclass_info": ecoclass_info}
    )


# TODO [#6]: Restrucutre FastAPI endpoints to seperate user-facing endpoints from internal endpoints
# refactor out the low level endpoints (/api) and rename others (this isn't really an `analysis` but it does compose a lot of logic like `analyze-burn`)
@app.post("/api/query-soil/analyze-ecoclass")
def analyze_ecoclass(
    body: QuerySoilPOSTBody, cloud_static_io_client: CloudStaticIOClient = Depends(get_cloud_static_io_client), __sentry = Depends(init_sentry)
):
    fire_event_name = body.fire_event_name
    geojson = json.loads(body.geojson)
    affiliation = body.affiliation

    sentry_sdk.set_context("analyze_ecoclass", {"request": body})

    try:
            
        mapunit_gdf = sdm_get_esa_mapunitid_poly(geojson)
        mu_polygon_keys = [
            mupolygonkey
            for __musym, __nationalmusym, __mukey, mupolygonkey in mapunit_gdf.index
        ]
        mrla_df = sdm_get_ecoclassid_from_mu_info(mu_polygon_keys)

        # join mapunitids with link table for ecoclassids
        mapunit_with_ecoclassid_df = mapunit_gdf.join(mrla_df).set_index("ecoclassid")

        edit_ecoclass_df_row_dicts = []
        ecoclass_ids = mrla_df["ecoclassid"].unique()

        n_ecoclasses = len(ecoclass_ids)
        n_within_edit = 0

        for ecoclass_id in ecoclass_ids:
            edit_success, edit_ecoclass_json = edit_get_ecoclass_info(ecoclass_id)
            if edit_success:
                n_within_edit += 1
                logger.log_text(f"Success: {ecoclass_id} exists within EDIT backend")
                edit_ecoclass_df_row_dict = edit_ecoclass_json["generalInformation"][
                    "dominantSpecies"
                ]
                edit_ecoclass_df_row_dict["ecoclassid"] = ecoclass_id
                edit_ecoclass_df_row_dicts.append(edit_ecoclass_df_row_dict)
            else:
                logger.log_text(
                    f"Missing: {edit_ecoclass_json} doesn't exist within EDIT backend"
                )

        logger.log_text(
            f"Found {n_within_edit} of {n_ecoclasses} ecoclasses ({100*round(n_within_edit/n_ecoclasses, 2)}%) within EDIT backend"
        )

        if n_within_edit > 0:
            edit_ecoclass_df = pd.DataFrame(edit_ecoclass_df_row_dicts).set_index(
                "ecoclassid"
            )
        else:
            # Populate with empty dataframe, for consistency's sake (so that the frontend doesn't have to handle this case)
            edit_ecoclass_df = pd.DataFrame(
                [],
                columns=[
                    "dominantTree1",
                    "dominantShrub1",
                    "dominantHerb1",
                    "dominantTree2",
                    "dominantShrub2",
                    "dominantHerb2",
                ],
            )

        # join ecoclassids with edit ecoclass info, to get spatial ecoclass info
        edit_ecoclass_geojson = mapunit_with_ecoclassid_df.join(
            edit_ecoclass_df, how="left"
        ).to_json()

        # save the ecoclass_geojson to the FTP server
        with tempfile.NamedTemporaryFile(suffix=".geojson", delete=False) as tmp:
            tmp_geojson_path = tmp.name
            with open(tmp_geojson_path, "w") as f:
                f.write(edit_ecoclass_geojson)

            cloud_static_io_client.upload(
                source_local_path=tmp_geojson_path,
                remote_path=f"public/{affiliation}/{fire_event_name}/ecoclass_dominant_cover.geojson",
            )

        logger.log_text(f"Ecoclass GeoJSON uploaded for {fire_event_name}")
        return f"Ecoclass GeoJSON uploaded for {fire_event_name}", 200

    except Exception as e:
        sentry_sdk.capture_exception(e)
        logger.log_text(f"Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


class AnaylzeRapPOSTBody(BaseModel):
    geojson: Any
    ignition_date: str
    fire_event_name: str
    affiliation: str

@app.post("/api/query-biomass/analyze-rap")
def analyze_rap(
    body: AnaylzeRapPOSTBody, cloud_static_io_client: CloudStaticIOClient = Depends(get_cloud_static_io_client), __sentry = Depends(init_sentry)
):
    boundary_geojson = json.loads(body.geojson)
    ignition_date = body.ignition_date
    fire_event_name = body.fire_event_name
    affiliation = body.affiliation

    sentry_sdk.set_context("analyze_rap", {"request": body})

    try:
        rap_estimates = rap_get_biomass(
            boundary_geojson=boundary_geojson,
            ignition_date=ignition_date
        )

        # save the cog to the FTP server
        cloud_static_io_client.upload_rap_estimates(
            rap_estimates=rap_estimates,
            affiliation=affiliation,
            fire_event_name=fire_event_name,
        )
        logger.log_text(f"RAP estimates uploaded for {fire_event_name}")

        return JSONResponse(
            status_code=200,
            content={
                "message": f"RAP estimates uploaded for {fire_event_name}",
                "fire_event_name": fire_event_name,
            },
        )

    except Exception as e:
        sentry_sdk.capture_exception(e)
        logger.log_text(f"Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/upload-shapefile-zip")
async def upload_shapefile(
    fire_event_name: str = Form(...),
    affiliation: str = Form(...),
    file: UploadFile = File(...),
    cloud_static_io_client: CloudStaticIOClient = Depends(get_cloud_static_io_client),
    __sentry = Depends(init_sentry)
):
    sentry_sdk.set_context("upload_shapefile", {"fire_event_name": fire_event_name, "affiliation": affiliation})

    try:
        # Read the file
        zip_content = await file.read()

        # Write the content to a temporary file
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            tmp.write(zip_content)
            tmp_zip = tmp.name

        valid_shp, __valid_tiff = ingest_esri_zip_file(tmp_zip)

        # For now assert that there is only one shapefile
        assert (
            len(valid_shp) == 1
        ), "Zip must contain exactly one shapefile (with associated files: .shx, .prj and optionally, .dbf)"
        __shp_paths, geojson = valid_shp[0]

        # Upload the zip and a geojson to SFTP
        cloud_static_io_client.upload(
            source_local_path=tmp_zip,
            remote_path=f"public/{affiliation}/{fire_event_name}/user_uploaded_{file.filename}",
        )

        with tempfile.NamedTemporaryFile(suffix=".geojson", delete=False) as tmp:
            tmp_geojson = tmp.name
            with open(tmp_geojson, "w") as f:
                f.write(geojson)
            cloud_static_io_client.upload(
                source_local_path=tmp_geojson,
                remote_path=f"public/{affiliation}/{fire_event_name}/boundary.geojson",
            )

        return JSONResponse(status_code=200, content={"geojson": geojson})

    except Exception as e:
        sentry_sdk.capture_exception(e)
        logger.log_text(f"Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/upload-drawn-aoi")
async def upload_drawn_aoi(
    fire_event_name: str = Form(...),
    affiliation: str = Form(...),
    geojson: str = Form(...),
    cloud_static_io_client: CloudStaticIOClient = Depends(get_cloud_static_io_client),
    __sentry = Depends(init_sentry)
):
    sentry_sdk.set_context("upload_drawn_aoi", {"fire_event_name": fire_event_name, "affiliation": affiliation})

    try:
        with tempfile.NamedTemporaryFile(suffix=".geojson", delete=False) as tmp:
            tmp_geojson = tmp.name
            with open(tmp_geojson, "w") as f:
                f.write(geojson)
            cloud_static_io_client.upload(
                source_local_path=tmp_geojson,
                remote_path=f"public/{affiliation}/{fire_event_name}/boundary.geojson",
            )
        return JSONResponse(status_code=200, content={"geojson": geojson})

    except Exception as e:
        sentry_sdk.capture_exception(e)
        logger.log_text(f"Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

class GetDerivedProductsPOSTBody(BaseModel):
    fire_event_name: str
    affiliation: str

@app.post("/api/get-derived-products")
async def get_derived_products(
    body: GetDerivedProductsPOSTBody,
    cloud_static_io_client: CloudStaticIOClient = Depends(get_cloud_static_io_client),
    __sentry = Depends(init_sentry)
):
    fire_event_name = body.fire_event_name
    affiliation = body.affiliation

    sentry_sdk.set_context("get_derived_products", {"fire_event_name": fire_event_name, "affiliation": affiliation})

    try:
        derived_products = cloud_static_io_client.get_derived_products(
            affiliation=affiliation, fire_event_name=fire_event_name
        )
        return JSONResponse(status_code=200, content=derived_products)

    except Exception as e:
        sentry_sdk.capture_exception(e)
        logger.log_text(f"Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

### WEB PAGES ###


@app.get(
    "/map/{affiliation}/{fire_event_name}/{burn_metric}", response_class=HTMLResponse
)
def serve_map(
    request: Request,
    fire_event_name: str,
    burn_metric: str,
    affiliation: str,
    manifest: dict = Depends(get_manifest),
):
    mapbox_token = get_mapbox_secret()

    tileserver_endpoint = os.getenv("GCP_CLOUD_RUN_ENDPOINT")
    # tileserver_endpoint = "http://localhost:5050"

    ## TODO [#21]: Use Tofu Output to construct hardocded cog and geojson urls (in case we change s3 bucket name)
    cog_url = f"https://burn-severity-backend.s3.us-east-2.amazonaws.com/public/{affiliation}/{fire_event_name}/{burn_metric}.tif"
    burn_boundary_geojson_url = f"https://burn-severity-backend.s3.us-east-2.amazonaws.com/public/{affiliation}/{fire_event_name}/boundary.geojson"
    ecoclass_geojson_url = f"https://burn-severity-backend.s3.us-east-2.amazonaws.com/public/{affiliation}/{fire_event_name}/ecoclass_dominant_cover.geojson"
    severity_obs_geojson_url = f"https://burn-severity-backend.s3.us-east-2.amazonaws.com/public/{affiliation}/{fire_event_name}/burn_field_observations.geojson"
    cog_tileserver_url_prefix = (
        tileserver_endpoint
        + f"/cog/tiles/WebMercatorQuad/{{z}}/{{x}}/{{y}}.png?url={cog_url}&nodata=-99&return_mask=true"
    )

    rap_cog_annual_url = f"https://burn-severity-backend.s3.us-east-2.amazonaws.com/public/{affiliation}/{fire_event_name}/rangeland_analysis_platform_annual_forb_and_grass.tif"
    rap_tileserver_annual_url = (
        tileserver_endpoint
        + f"/cog/tiles/WebMercatorQuad/{{z}}/{{x}}/{{y}}.png?url={rap_cog_annual_url}&nodata=-99&return_mask=true"
    )

    rap_cog_perennial_url = f"https://burn-severity-backend.s3.us-east-2.amazonaws.com/public/{affiliation}/{fire_event_name}/rangeland_analysis_platform_perennial_forb_and_grass.tif"
    rap_tileserver_perennial_url = (
        tileserver_endpoint
        + f"/cog/tiles/WebMercatorQuad/{{z}}/{{x}}/{{y}}.png?url={rap_cog_perennial_url}&nodata=-99&return_mask=true"
    )

    rap_cog_shrub_url = f"https://burn-severity-backend.s3.us-east-2.amazonaws.com/public/{affiliation}/{fire_event_name}/rangeland_analysis_platform_shrub.tif"
    rap_tileserver_shrub_url = (
        tileserver_endpoint
        + f"/cog/tiles/WebMercatorQuad/{{z}}/{{x}}/{{y}}.png?url={rap_cog_shrub_url}&nodata=-99&return_mask=true"
    )

    rap_cog_tree_url = f"https://burn-severity-backend.s3.us-east-2.amazonaws.com/public/{affiliation}/{fire_event_name}/rangeland_analysis_platform_tree.tif"
    rap_tileserver_tree_url = (
        tileserver_endpoint
        + f"/cog/tiles/WebMercatorQuad/{{z}}/{{x}}/{{y}}.png?url={rap_cog_tree_url}&nodata=-99&return_mask=true"
    )


    fire_metadata = manifest[fire_event_name]
    fire_metadata_json = json.dumps(fire_metadata)

    with open("src/static/map/burn_metric_text.json") as json_file:
        burn_metric_text = json.load(json_file)

    return templates.TemplateResponse(
        "map/map.html",
        {
            "request": request,
            "mapbox_token": mapbox_token,  # for NAIP and Satetllite in V0
            "fire_event_name": fire_event_name,
            "burn_metric": burn_metric,
            "burn_metric_text": burn_metric_text,
            "fire_metadata_json": fire_metadata_json,
            "cog_tileserver_url_prefix": cog_tileserver_url_prefix,
            "burn_boundary_geojson_url": burn_boundary_geojson_url,
            "ecoclass_geojson_url": ecoclass_geojson_url,
            "severity_obs_geojson_url": severity_obs_geojson_url,
            "rap_tileserver_annual_url": rap_tileserver_annual_url,
            "rap_tileserver_perennial_url": rap_tileserver_perennial_url,
            "rap_tileserver_shrub_url": rap_tileserver_shrub_url,
            "rap_tileserver_tree_url": rap_tileserver_tree_url,
        },
    )


@app.get("/upload", response_class=HTMLResponse)
def upload(request: Request):
    mapbox_token = get_mapbox_secret()
    tileserver_endpoint = os.getenv("GCP_CLOUD_RUN_ENDPOINT")

    return templates.TemplateResponse(
        "upload/upload.html",
        {
            "request": request,
            "mapbox_token": mapbox_token,  # for NAIP and Satetllite in V0
            "tileserver_endpoint": tileserver_endpoint,
        }
    )

@app.get("/directory", response_class=HTMLResponse)
def directory(request: Request, manifest: dict = Depends(get_manifest)):
    mapbox_token = get_mapbox_secret()
    manifest_json = json.dumps(manifest)
    cloud_run_endpoint = os.getenv("GCP_CLOUD_RUN_ENDPOINT")
    return templates.TemplateResponse(
        "directory/directory.html",
        {
            "request": request,
            "manifest": manifest_json,
            "mapbox_token": mapbox_token,
            "cloud_run_endpoint": cloud_run_endpoint
        }
    )

@app.get("/sketch", response_class=HTMLResponse)
def sketch(request: Request):
    return templates.TemplateResponse("sketch/sketch.html", {"request": request})
