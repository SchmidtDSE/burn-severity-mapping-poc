from fastapi import Depends, APIRouter, HTTPException, Form
from fastapi.responses import JSONResponse
from logging import Logger
import tempfile
import sentry_sdk

from ..dependencies import get_cloud_logger, get_cloud_static_io_client, init_sentry
from src.util.cloud_static_io import CloudStaticIOClient

router = APIRouter()


@router.post(
    "/api/upload/drawn-aoi",
    tags=["upload"],
    description="Upload a drawn AOI boundary to cloud storage",
)
async def upload_drawn_aoi(
    fire_event_name: str = Form(...),
    affiliation: str = Form(...),
    geojson: str = Form(...),
    cloud_static_io_client: CloudStaticIOClient = Depends(get_cloud_static_io_client),
    logger: Logger = Depends(get_cloud_logger),
    __sentry: None = Depends(init_sentry),
):
    """
    Uploads a drawn area of interest (AOI) in GeoJSON format to the cloud storage.

    Args:
        fire_event_name (str): The name of the fire event.
        affiliation (str): The affiliation of the user.
        geojson (str): The GeoJSON representation of the drawn AOI.
        cloud_static_io_client (CloudStaticIOClient): The client for interacting with the cloud storage. FastAPI handles this as a dependency injection.
        __sentry (None, optional): Sentry client, just needs to be initialized. FastAPI handles this as a dependency injection.
        logger (Logger, optional): Google cloud logger. FastAPI handles this as a dependency injection.

    Returns:
        JSONResponse: The response containing the uploaded GeoJSON.

    Raises:
        HTTPException: If there is an error during the upload process.
    """
    sentry_sdk.set_context(
        "upload_drawn_aoi",
        {"fire_event_name": fire_event_name, "affiliation": affiliation},
    )

    try:
        main(
            fire_event_name=fire_event_name,
            affiliation=affiliation,
            geojson=geojson,
            cloud_static_io_client=cloud_static_io_client,
            logger=logger,
        )
        return JSONResponse(status_code=200, content={"geojson": geojson})

    except Exception as e:
        sentry_sdk.capture_exception(e)
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


def main(
    fire_event_name: str,
    affiliation: str,
    geojson: str,
    cloud_static_io_client: CloudStaticIOClient,
    logger: Logger,
):
    with tempfile.NamedTemporaryFile(suffix=".geojson", delete=False) as tmp:
        tmp_geojson = tmp.name
        with open(tmp_geojson, "w") as f:
            f.write(geojson)
        cloud_static_io_client.upload(
            source_local_path=tmp_geojson,
            remote_path=f"public/{affiliation}/{fire_event_name}/drawn_aoi_boundary.geojson",
        )
