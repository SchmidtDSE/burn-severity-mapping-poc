from fastapi import Depends, APIRouter, Request
from fastapi.responses import HTMLResponse
import os
from fastapi.templating import Jinja2Templates

from ..dependencies import get_mapbox_secret

router = APIRouter()
templates = Jinja2Templates(directory="src/static")


@router.get("/upload", response_class=HTMLResponse)
def upload(request: Request, mapbox_token: str = Depends(get_mapbox_secret)):
    tileserver_endpoint = os.getenv("GCP_CLOUD_RUN_ENDPOINT")

    return templates.TemplateResponse(
        "upload/upload.html",
        {
            "request": request,
            "mapbox_token": mapbox_token,  # for NAIP and Satetllite in V0
            "tileserver_endpoint": tileserver_endpoint,
        },
    )
