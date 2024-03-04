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

from src.routers.analyze.spectral_burn_metrics import (
    main as analyze_spectral_burn_metrics,
)
from src.routers.fetch.ecoclass import main as fetch_ecoclass
from src.routers.upload.shapefile_zip import main as upload_shapefile_zip

# from src.routers.upload.drawn_aoi import main as upload_drawn_aoi


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

    ## TODO: Should probably define a class for batch analysis and fetch
    analyze_spectral_burn_metrics(
        geojson_boundary=geojson_boundary,
        date_ranges=date_ranges,
        fire_event_name=fire_event_name,
        affiliation=affiliation,
        derive_boundary=derive_boundary,
        logger=logger,
        cloud_static_io_client=cloud_static_io_client,
    )

    fetch_ecoclass(
        fire_event_name=fire_event_name,
        geojson_boundary=geojson_boundary,
        affiliation=affiliation,
        cloud_static_io_client=cloud_static_io_client,
        logger=logger,
    )
