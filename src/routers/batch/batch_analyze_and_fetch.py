from ..dependencies import get_cloud_logger, get_cloud_static_io_client, init_sentry
from src.lib.query_sentinel import Sentinel2Client, NoFireBoundaryDetectedError
from fastapi import Depends, APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from src.util.cloud_static_io import CloudStaticIOClient
from pydantic import BaseModel
from logging import Logger
from typing import Any
import json
import datetime
import tempfile

from src.routers.analyze.spectral_burn_metrics import (
    main as analyze_spectral_burn_metrics,
)
from src.routers.fetch.ecoclass import main as fetch_ecoclass
from src.routers.upload.shapefile_zip import main as upload_shapefile_zip
from src.routers.upload.drawn_aoi import main as upload_drawn_aoi
from src.routers.fetch.rangeland_analysis_platform import main as fetch_rap

router = APIRouter()


class BatchAnalyzeAndFetchPOSTBody(BaseModel):
    """
    Represents the request body for analyzing burn metrics.

    Attributes:
        geojson (str): The GeoJSON data in string format.
        derive_boundary (bool): Flag indicating whether to derive the boundary. If a shapefile is provided, this will be False.
            If an AOI is drawn, this will be True.
        date_ranges (dict): The date ranges for analysis.
        fire_event_name (str): The name of the fire event.
        affiliation (str): The affiliation of the analysis.
    """

    geojson: Any
    ignition_date: str
    containment_date: str
    time_buffer_days: int
    fire_event_name: str
    affiliation: str
    derive_boundary: bool = False


@router.post("/batch/analyze_and_fetch")
def analyze_and_fetch(
    body: BatchAnalyzeAndFetchPOSTBody,
    sentry: None = Depends(init_sentry),
    logger: Logger = Depends(get_cloud_logger),
    cloud_static_io_client: CloudStaticIOClient = Depends(get_cloud_static_io_client),
):

    try:

        geojson_boundary = json.loads(body.geojson)

        fire_event_name = body.fire_event_name
        affiliation = body.affiliation
        ignition_date = body.ignition_date
        containment_date = body.containment_date
        time_buffer_days = body.time_buffer_days
        derive_boundary = body.derive_boundary

        ignition_date = datetime.datetime.strptime(ignition_date, "%Y-%m-%dT%H:%M:%S%z")
        containment_date = datetime.datetime.strptime(
            containment_date, "%Y-%m-%dT%H:%M:%S%z"
        )

        main(
            geojson_boundary=geojson_boundary,
            fire_event_name=fire_event_name,
            affiliation=affiliation,
            derive_boundary=derive_boundary,
            logger=logger,
            cloud_static_io_client=cloud_static_io_client,
            ignition_date=ignition_date,
            containment_date=containment_date,
            time_buffer_days=time_buffer_days,
        )

        return JSONResponse(
            status_code=200,
            content={
                "message": f"Analyze and fetch job has been completed successfully for fire event {fire_event_name}"
            },
        )

    except NoFireBoundaryDetectedError as e:
        logger.warning("No fire boundary detected")
        return JSONResponse(
            status_code=204,
            content={"message": "No fire boundary detected", "error": str(e)},
        )

    except Exception as e:
        sentry.capture_exception(e)
        logger.error("An error occurred while analyzing and fetching Sentinel-2 data")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while analyzing and fetching for fire event {fire_event_name}",
        )


def main(
    geojson_boundary: Any,
    fire_event_name: str,
    affiliation: str,
    derive_boundary: bool,
    logger: Logger,
    cloud_static_io_client: CloudStaticIOClient,
    ignition_date: datetime.datetime,
    containment_date: datetime.datetime,
    time_buffer_days: int,
):

    # convert time buffer days to timedelta, adjust, and convert back to string

    submission_time = datetime.datetime.now()
    time_buffer_days = datetime.timedelta(days=time_buffer_days)
    prefire_range = [
        (ignition_date - time_buffer_days).strftime("%Y-%m-%d"),
        (ignition_date).strftime("%Y-%m-%d"),
    ]
    postfire_range = [
        (containment_date).strftime("%Y-%m-%d"),
        (containment_date + time_buffer_days).strftime("%Y-%m-%d"),
    ]
    date_ranges = {
        "prefire": prefire_range,
        "postfire": postfire_range,
    }
    geojson_name = "drawn_aoi_boundary" if derive_boundary else "boundary"

    ## TODO: Should probably define a class for batch analysis and fetch

    job_status = {
        "submitted": submission_time,
        "fire_event_name": fire_event_name,
        "affiliation": affiliation,
        "upload": {},
        "analyze_spectral_metrics": {},
        "fetch_ecoclass": {},
        "fetch_rap": {},
    }

    try:
        # First upload the geojson to s3
        with tempfile.NamedTemporaryFile(suffix=".geojson", delete=False) as tmp:
            tmp_geojson = tmp.name
            with open(tmp_geojson, "w") as f:
                f.write(json.dumps(geojson_boundary))
            boundary_s3_path = (
                f"public/{affiliation}/{fire_event_name}/{geojson_name}.geojson"
            )
            cloud_static_io_client.upload(
                source_local_path=tmp_geojson,
                remote_path=boundary_s3_path,
            )

    except Exception as e:
        logger.log_text(
            f"An error occurred while uploading the geojson boundary for fire event {fire_event_name}: {e}"
        )

    time_elapsed = datetime.datetime.now() - submission_time
    job_status["upload"]["time_elapsed"] = str(time_elapsed)
    upload_done_time = datetime.datetime.now()

    try:
        # Then analyze the spectral burn metrics
        analyze_spectral_burn_metrics(
            geojson_boundary=geojson_boundary,
            date_ranges=date_ranges,
            fire_event_name=fire_event_name,
            affiliation=affiliation,
            derive_boundary=derive_boundary,
            logger=logger,
            cloud_static_io_client=cloud_static_io_client,
        )

    except Exception as e:
        logger.log_text(
            f"An error occurred while analyzing spectral burn metrics for fire event {fire_event_name}: {e}"
        )
        job_status["analyze_spectral_metrics"]["error"] = e

    time_elapsed = datetime.datetime.now() - upload_done_time
    job_status["analyze_spectral_metrics"]["time_elapsed"] = str(time_elapsed)
    analysis_done_time = datetime.datetime.now()

    try:
        # Then first fetch the ecoclass data
        fetch_ecoclass(
            fire_event_name=fire_event_name,
            geojson_boundary=geojson_boundary,
            affiliation=affiliation,
            cloud_static_io_client=cloud_static_io_client,
            logger=logger,
        )

    except Exception as e:
        logger.log_text(
            f"An error occurred while fetching ecoclass data for fire event {fire_event_name}: {e}"
        )
        job_status["fetch_ecoclass"]["error"] = e

    time_elapsed = datetime.datetime.now() - analysis_done_time
    job_status["fetch_ecoclass"]["time_elapsed"] = str(time_elapsed)
    fetch_ecoclass_done_time = datetime.datetime.now()

    try:
        # Last, fetch rangeland analysis platform
        fetch_rap(
            geojson_boundary=geojson_boundary,
            fire_event_name=fire_event_name,
            affiliation=affiliation,
            cloud_static_io_client=cloud_static_io_client,
            logger=logger,
        )

    except Exception as e:
        logger.log_text(
            f"An error occurred while fetching rangeland analysis platform data for fire event {fire_event_name}: {e}"
        )
        job_status["fetch_rap"]["error"] = e

    time_elapsed = datetime.datetime.now() - fetch_ecoclass_done_time
    job_status["fetch_rap"]["time_elapsed"] = str(time_elapsed)
    fetch_rap_done_time = datetime.datetime.now()

    total_time_elapsed = datetime.datetime.now() - submission_time
    logger.log_text(
        f"Batch analyze and fetch job status for fire event {fire_event_name} in {total_time_elapsed}: {job_status}"
    )

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp_json = f.name
        with open(tmp_json, "r") as f:
            f.write(json.dumps(job_status))
        log_s3_path = f"logs/{affiliation}/{fire_event_name}/job_status_{str(submission_time)}.json"
        cloud_static_io_client.upload(
            source_local_path=tmp_json, remote_path=log_s3_path
        )
