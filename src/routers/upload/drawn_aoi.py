from fastapi import Depends, APIRouter, HTTPException, Form
from fastapi.responses import JSONResponse
from logging import Logger
import tempfile
import sentry_sdk

from ..dependencies import get_cloud_logger, get_cloud_static_io_client, init_sentry
from src.util.cloud_static_io import CloudStaticIOClient

router = APIRouter()

@router.post("/api/upload-drawn-aoi", tags=["upload"], description="Upload a drawn AOI boundary to cloud storage")
async def upload_drawn_aoi(
    fire_event_name: str = Form(...),
    affiliation: str = Form(...),
    geojson: str = Form(...),
    cloud_static_io_client: CloudStaticIOClient = Depends(get_cloud_static_io_client),
    logger: Logger = Depends(get_cloud_logger),
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
                remote_path=f"public/{affiliation}/{fire_event_name}/drawn_aoi_boundary.geojson",
            )
        return JSONResponse(status_code=200, content={"geojson": geojson})

    except Exception as e:
        sentry_sdk.capture_exception(e)
        logger.log_text(f"Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
