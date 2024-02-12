
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

@router.post("/api/upload-shapefile-zip")
async def upload_shapefile(
    fire_event_name: str = Form(...),
    affiliation: str = Form(...),
    file: UploadFile = File(...),
    cloud_static_io_client: CloudStaticIOClient = Depends(get_cloud_static_io_client),
    logger: Logger = Depends(get_cloud_logger),
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

