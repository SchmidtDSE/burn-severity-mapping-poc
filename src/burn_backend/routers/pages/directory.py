from fastapi import Depends, APIRouter, Request
from fastapi.responses import HTMLResponse
import os
from fastapi.templating import Jinja2Templates
import json
from ..dependencies import get_mapbox_secret, get_manifest

router = APIRouter()
templates = Jinja2Templates(directory="src/static")


@router.get("/directory", response_class=HTMLResponse)
def directory(
    request: Request,
    manifest: dict = Depends(get_manifest),
    mapbox_token: str = Depends(get_mapbox_secret),
):
    manifest_json = json.dumps(manifest)
    cloud_run_endpoint_titiler = os.getenv("GCP_CLOUD_RUN_ENDPOINT_TITILER")
    return templates.TemplateResponse(
        "directory/directory.html",
        {
            "request": request,
            "manifest": manifest_json,
            "mapbox_token": mapbox_token,
            "cloud_run_endpoint": cloud_run_endpoint,
        },
    )
