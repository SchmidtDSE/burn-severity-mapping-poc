from fastapi import Depends, APIRouter, HTTPException, Form, File, UploadFile
from fastapi.responses import JSONResponse
from logging import Logger
from typing import Any
from pydantic import BaseModel
import tempfile
import sentry_sdk

from ..dependencies import get_cloud_logger, get_cloud_static_io_client, init_sentry
from src.util.cloud_static_io import CloudStaticIOClient
from src.util.ingest_burn_zip import ingest_esri_zip_file

router = APIRouter()


@router.post(
    "/api/upload/shapefile-zip",
    tags=["upload"],
    description="Upload a shapefile zip of a predefined fire event area",
)
async def upload_shapefile(
    fire_event_name: str = Form(...),
    affiliation: str = Form(...),
    file: UploadFile = File(...),
    cloud_static_io_client: CloudStaticIOClient = Depends(get_cloud_static_io_client),
    logger: Logger = Depends(get_cloud_logger),
    __sentry: None = Depends(init_sentry),
):
    """
    Uploads a shapefile to a remote storage location.

    Args:
        fire_event_name (str): The name of the fire event.
        affiliation (str): The affiliation of the uploader.
        file (UploadFile): The shapefile to be uploaded.
        cloud_static_io_client (CloudStaticIOClient): The client for interacting with the remote storage. FastAPI handles this as a dependency injection.
        __sentry (None, optional): Sentry client, just needs to be initialized. FastAPI handles this as a dependency injection.
        logger (Logger, optional): Google cloud logger. FastAPI handles this as a dependency injection.

    Returns:
        JSONResponse: The response containing the uploaded geojson.

    Raises:
        HTTPException: If there is an error during the upload process.
    """
    sentry_sdk.set_context(
        "upload_shapefile",
        {"fire_event_name": fire_event_name, "affiliation": affiliation},
    )

    try:
        # Read the file
        zip_content = await file.read()

        # Write the content to a temporary file
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            tmp.write(zip_content)
            tmp_zip = tmp.name

        return main(
            zip_path=tmp_zip,
            fire_event_name=fire_event_name,
            affiliation=affiliation,
            file=file,
            cloud_static_io_client=cloud_static_io_client,
            logger=logger,
        )

    except Exception as e:
        sentry_sdk.capture_exception(e)
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


def main(
    zip_path: str,
    fire_event_name: str,
    affiliation: str,
    file: UploadFile,
    cloud_static_io_client: CloudStaticIOClient,
    logger: Logger,
):

    user_uploaded_s3_path = (
        f"public/{affiliation}/{fire_event_name}/user_uploaded_{file.filename}"
    )
    # Upload the zip and a geojson to s3
    cloud_static_io_client.upload(
        source_local_path=zip_path,
        remote_path=user_uploaded_s3_path,
    )

    logger.info(f"Uploaded zip file ({user_uploaded_s3_path})")

    valid_shp, __valid_tiff = ingest_esri_zip_file(zip_path)

    # For now assert that there is only one shapefile
    assert (
        len(valid_shp) == 1
    ), "Zip must contain exactly one shapefile (with associated files: .shx, .prj and optionally, .dbf)"
    __shp_paths, geojson = valid_shp[0]

    with tempfile.NamedTemporaryFile(suffix=".geojson", delete=False) as tmp:
        tmp_geojson = tmp.name
        with open(tmp_geojson, "w") as f:
            f.write(geojson)
        boundary_s3_path = f"public/{affiliation}/{fire_event_name}/boundary.geojson"
        cloud_static_io_client.upload(
            source_local_path=tmp_geojson,
            remote_path=boundary_s3_path,
        )

    logger.info(f"Uploaded geojson file ({boundary_s3_path})")

    return JSONResponse(status_code=200, content={"geojson": geojson})
