from fastapi import Depends, APIRouter, Request
from fastapi.responses import HTMLResponse
import os
from fastapi.templating import Jinja2Templates

from ..dependencies import get_mapbox_secret, get_manifest

router = APIRouter()
templates = Jinja2Templates(directory="src/static")


@router.get("/upload", response_class=HTMLResponse)
def upload(
    request: Request,
    mapbox_token: str = Depends(get_mapbox_secret),
):
    tileserver_endpoint = os.getenv("GCP_CLOUD_RUN_ENDPOINT_BURN_BACKEND")
    ## TODO: These thresholds should be configurable, and probably should use the same
    ## frontend elements as the threhsold sliders within the map. Going to punt on that for now,
    ## since the map needs a refactor in the vein of the upload refactor.
    cog_tileserver_url_prefix = (
        tileserver_endpoint
        + '/cog/tiles/WebMercatorQuad/{z}/{x}/{y}.png?nodata=-99&return_mask=true&algorithm=censor_and_scale&algorithm_params={"thresholds":{"min":-0.025,"max":0.5}}&url='
    )

    return templates.TemplateResponse(
        "upload/upload.html",
        {
            "request": request,
            "mapbox_token": mapbox_token,  # for NAIP and Satetllite in V0
            "cog_tileserver_url_prefix": cog_tileserver_url_prefix,
        },
    )
