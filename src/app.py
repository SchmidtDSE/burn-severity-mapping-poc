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

from src.routers.debug import (
    health,
    trigger_error,
    check_connectivity,
    check_dns
)
from src.routers.analysis import (
    analyze_fire_event
)

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

app = FastAPI(docs_url="/documentation")
app.include_router(health.router)
app.include_router(trigger_error.router)

cog = TilerFactory(process_dependency=algorithms.dependency)
app.include_router(cog.router, prefix="/cog", tags=["Cloud Optimized GeoTIFF"])
add_exception_handlers(app, DEFAULT_STATUS_CODES)

app.mount("/static", StaticFiles(directory="src/static"), name="static")
templates = Jinja2Templates(directory="src/static")

### DEBUG ###
app.include_router(health.router)
app.include_router(trigger_error.router)
app.include_router(check_connectivity.router)
app.include_router(check_dns.router)

### API ENDPOINTS ###

app.include_router(analyze_fire_event.router)

# class QuerySoilPOSTBody(BaseModel):
#     geojson: Any
#     fire_event_name: str
#     affiliation: str


# @app.post("/api/query-soil/get-esa-mapunitid-poly")
# def get_esa_mapunitid_poly(body: QuerySoilPOSTBody):
#     geojson = body.geojson
#     fire_event_name = body.fire_event_name
#     mapunitpoly_geojson = sdm_get_esa_mapunitid_poly(geojson)
#     return JSONResponse(
#         status_code=200,
#         content={"mapunitpoly_geojson": json.loads(mapunitpoly_geojson)},
#     )
#     # return polygon_response


# class MUPair(BaseModel):
#     mu_pair: Tuple[str, str]


# class QueryEcoclassidPOSTBody(BaseModel):
#     mu_pair_tuples: List[MUPair]


# @app.post("/api/query-soil/get-ecoclassid-from-mu-info")
# def get_ecoclassid_from_mu_info(body: QueryEcoclassidPOSTBody):
#     mu_pair_tuples = body.mu_pair_tuples
#     mrla = sdm_get_ecoclassid_from_mu_info(mu_pair_tuples)
#     return JSONResponse(status_code=200, content={"mrla": json.loads(mrla)})


# @app.get("/api/query-soil/get-ecoclass-info")
# def get_ecoclass_info(ecoclassid: str = Query(...)):
#     status_code, ecoclass_info = edit_get_ecoclass_info(ecoclassid)
#     return JSONResponse(
#         status_code=status_code, content={"ecoclass_info": ecoclass_info}
#     )


# # TODO [#6]: Restrucutre FastAPI endpoints to seperate user-facing endpoints from internal endpoints
# # refactor out the low level endpoints (/api) and rename others (this isn't really an `analysis` but it does compose a lot of logic like `analyze-burn`)
# @app.post("/api/query-soil/analyze-ecoclass")
# def analyze_ecoclass(
#     body: QuerySoilPOSTBody, cloud_static_io_client: CloudStaticIOClient = Depends(get_cloud_static_io_client), __sentry = Depends(init_sentry)
# ):
#     fire_event_name = body.fire_event_name
#     geojson = json.loads(body.geojson)
#     affiliation = body.affiliation

#     sentry_sdk.set_context("analyze_ecoclass", {"request": body})

#     try:
            
#         mapunit_gdf = sdm_get_esa_mapunitid_poly(geojson)
#         mu_polygon_keys = [
#             mupolygonkey
#             for __musym, __nationalmusym, __mukey, mupolygonkey in mapunit_gdf.index
#         ]
#         mrla_df = sdm_get_ecoclassid_from_mu_info(mu_polygon_keys)

#         # join mapunitids with link table for ecoclassids
#         mapunit_with_ecoclassid_df = mapunit_gdf.join(mrla_df).set_index("ecoclassid")

#         edit_ecoclass_df_row_dicts = []
#         ecoclass_ids = mrla_df["ecoclassid"].unique()

#         n_ecoclasses = len(ecoclass_ids)
#         n_within_edit = 0

#         for ecoclass_id in ecoclass_ids:
#             edit_success, edit_ecoclass_json = edit_get_ecoclass_info(ecoclass_id)
#             if edit_success:
#                 n_within_edit += 1
#                 logger.log_text(f"Success: {ecoclass_id} exists within EDIT backend")
#                 edit_ecoclass_df_row_dict = edit_ecoclass_json["generalInformation"][
#                     "dominantSpecies"
#                 ]
#                 edit_ecoclass_df_row_dict["ecoclassid"] = ecoclass_id
#                 edit_ecoclass_df_row_dicts.append(edit_ecoclass_df_row_dict)
#             else:
#                 logger.log_text(
#                     f"Missing: {edit_ecoclass_json} doesn't exist within EDIT backend"
#                 )

#         logger.log_text(
#             f"Found {n_within_edit} of {n_ecoclasses} ecoclasses ({100*round(n_within_edit/n_ecoclasses, 2)}%) within EDIT backend"
#         )

#         if n_within_edit > 0:
#             edit_ecoclass_df = pd.DataFrame(edit_ecoclass_df_row_dicts).set_index(
#                 "ecoclassid"
#             )
#         else:
#             # Populate with empty dataframe, for consistency's sake (so that the frontend doesn't have to handle this case)
#             edit_ecoclass_df = pd.DataFrame(
#                 [],
#                 columns=[
#                     "dominantTree1",
#                     "dominantShrub1",
#                     "dominantHerb1",
#                     "dominantTree2",
#                     "dominantShrub2",
#                     "dominantHerb2",
#                 ],
#             )

#         # join ecoclassids with edit ecoclass info, to get spatial ecoclass info
#         edit_ecoclass_geojson = mapunit_with_ecoclassid_df.join(
#             edit_ecoclass_df, how="left"
#         ).to_json()

#         # save the ecoclass_geojson to the FTP server
#         with tempfile.NamedTemporaryFile(suffix=".geojson", delete=False) as tmp:
#             tmp_geojson_path = tmp.name
#             with open(tmp_geojson_path, "w") as f:
#                 f.write(edit_ecoclass_geojson)

#             cloud_static_io_client.upload(
#                 source_local_path=tmp_geojson_path,
#                 remote_path=f"public/{affiliation}/{fire_event_name}/ecoclass_dominant_cover.geojson",
#             )

#         logger.log_text(f"Ecoclass GeoJSON uploaded for {fire_event_name}")
#         return f"Ecoclass GeoJSON uploaded for {fire_event_name}", 200

#     except Exception as e:
#         sentry_sdk.capture_exception(e)
#         logger.log_text(f"Error: {e}")
#         raise HTTPException(status_code=400, detail=str(e))


# class AnaylzeRapPOSTBody(BaseModel):
#     geojson: Any
#     ignition_date: str
#     fire_event_name: str
#     affiliation: str

# @app.post("/api/query-biomass/analyze-rap")
# def analyze_rap(
#     body: AnaylzeRapPOSTBody, cloud_static_io_client: CloudStaticIOClient = Depends(get_cloud_static_io_client), __sentry = Depends(init_sentry)
# ):
#     boundary_geojson = json.loads(body.geojson)
#     ignition_date = body.ignition_date
#     fire_event_name = body.fire_event_name
#     affiliation = body.affiliation

#     sentry_sdk.set_context("analyze_rap", {"request": body})

#     try:
#         rap_estimates = rap_get_biomass(
#             boundary_geojson=boundary_geojson,
#             ignition_date=ignition_date
#         )

#         # save the cog to the FTP server
#         cloud_static_io_client.upload_rap_estimates(
#             rap_estimates=rap_estimates,
#             affiliation=affiliation,
#             fire_event_name=fire_event_name,
#         )
#         logger.log_text(f"RAP estimates uploaded for {fire_event_name}")

#         return JSONResponse(
#             status_code=200,
#             content={
#                 "message": f"RAP estimates uploaded for {fire_event_name}",
#                 "fire_event_name": fire_event_name,
#             },
#         )

#     except Exception as e:
#         sentry_sdk.capture_exception(e)
#         logger.log_text(f"Error: {e}")
#         raise HTTPException(status_code=400, detail=str(e))


# @app.post("/api/upload-drawn-aoi")
# async def upload_drawn_aoi(
#     fire_event_name: str = Form(...),
#     affiliation: str = Form(...),
#     geojson: str = Form(...),
#     cloud_static_io_client: CloudStaticIOClient = Depends(get_cloud_static_io_client),
#     __sentry = Depends(init_sentry)
# ):
#     sentry_sdk.set_context("upload_drawn_aoi", {"fire_event_name": fire_event_name, "affiliation": affiliation})

#     try:
#         with tempfile.NamedTemporaryFile(suffix=".geojson", delete=False) as tmp:
#             tmp_geojson = tmp.name
#             with open(tmp_geojson, "w") as f:
#                 f.write(geojson)
#             cloud_static_io_client.upload(
#                 source_local_path=tmp_geojson,
#                 remote_path=f"public/{affiliation}/{fire_event_name}/boundary.geojson",
#             )
#         return JSONResponse(status_code=200, content={"geojson": geojson})

#     except Exception as e:
#         sentry_sdk.capture_exception(e)
#         logger.log_text(f"Error: {e}")
#         raise HTTPException(status_code=400, detail=str(e))

# class GetDerivedProductsPOSTBody(BaseModel):
#     fire_event_name: str
#     affiliation: str

# @app.post("/api/get-derived-products")
# async def get_derived_products(
#     body: GetDerivedProductsPOSTBody,
#     cloud_static_io_client: CloudStaticIOClient = Depends(get_cloud_static_io_client),
#     __sentry = Depends(init_sentry)
# ):
#     fire_event_name = body.fire_event_name
#     affiliation = body.affiliation

#     sentry_sdk.set_context("get_derived_products", {"fire_event_name": fire_event_name, "affiliation": affiliation})

#     try:
#         derived_products = cloud_static_io_client.get_derived_products(
#             affiliation=affiliation, fire_event_name=fire_event_name
#         )
#         return JSONResponse(status_code=200, content=derived_products)

#     except Exception as e:
#         sentry_sdk.capture_exception(e)
#         logger.log_text(f"Error: {e}")
#         raise HTTPException(status_code=400, detail=str(e))

# ### WEB PAGES ###


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