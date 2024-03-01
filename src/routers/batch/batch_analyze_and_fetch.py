from ..dependencies import get_cloud_logger, get_cloud_static_io_client, init_sentry
from src.lib.query_sentinel import Sentinel2Client, NoFireBoundaryDetectedError
from fastapi import Depends, APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from src.util.cloud_static_io import CloudStaticIOClient
from pydantic import BaseModel
from logging import Logger
from typing import Any
import json

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

        

    except NoFireBoundaryDetectedError as e:
        logger.warning("No fire boundary detected")
    except Exception as e:
        sentry.capture_exception(e)
        logger.error("An error occurred while analyzing and fetching Sentinel-2 data")
        raise e