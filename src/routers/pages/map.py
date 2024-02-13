from fastapi import Depends, APIRouter, Request
from fastapi.responses import HTMLResponse
import os
import json
from fastapi.templating import Jinja2Templates

from ..dependencies import get_manifest, get_mapbox_secret

router = APIRouter()
templates = Jinja2Templates(directory="src/static")

@router.get(
    "/map/{affiliation}/{fire_event_name}/{burn_metric}", response_class=HTMLResponse
)
def serve_map(
    request: Request,
    fire_event_name: str,
    burn_metric: str,
    affiliation: str,
    manifest: dict = Depends(get_manifest),
    mapbox_token: str = Depends(get_mapbox_secret),
):

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


    fire_metadata = manifest[affiliation][fire_event_name]
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
