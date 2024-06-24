from fastapi import Depends, APIRouter, HTTPException
from fastapi.responses import JSONResponse
from logging import Logger
from typing import Any
from pydantic import BaseModel
import sentry_sdk
import json
import time
from ..dependencies import get_cloud_logger, get_cloud_static_io_client, init_sentry
from src.burn_backend.lib.query_rap import (
    rap_get_biomass,
)
from src.common.util.cloud_static_io import CloudStaticIOClient

router = APIRouter()


class FetchRapPOSTBody(BaseModel):
    """
    Represents the request body for fetching Rangeland Analysis Platform (RAP) data.

    Attributes:
        geojson (str): The GeoJSON data for the analysis.
        ignition_date (str): The date of ignition for the fire event.
        fire_event_name (str): The name of the fire event.
        affiliation (str): The affiliation associated with the analysis.
    """

    geojson: Any
    ignition_date: str
    fire_event_name: str
    affiliation: str


@router.post(
    "/api/fetch/rangeland-analysis-platform",
    tags=["fetch"],
    description="Fetch Rangeland Analysis Platform (RAP) biomass estimates",
)
def fetch_rangeland_analysis_platform(
    body: FetchRapPOSTBody,
    cloud_static_io_client: CloudStaticIOClient = Depends(get_cloud_static_io_client),
    __sentry: None = Depends(init_sentry),
    logger: Logger = Depends(get_cloud_logger),
):
    """
    Fetches rangeland data for a given fire event, withing the given boundary.

    Args:
        body (AnaylzeRapPOSTBody): The request body containing the necessary data for analysis.
        cloud_static_io_client (CloudStaticIOClient, optional): The client for interacting with the cloud storage service. FastAPI handles this as a dependency injection.
        __sentry (None, optional): Sentry client, just needs to be initialized. FastAPI handles this as a dependency injection.
        logger (Logger, optional): Google cloud logger. FastAPI handles this as a dependency injection.

    Returns:
        JSONResponse: The response containing the status and message.
    """
    geojson_boundary = body.geojson
    ignition_date = body.ignition_date
    fire_event_name = body.fire_event_name
    affiliation = body.affiliation

    sentry_sdk.set_context("analyze_rap", {"request": body})
    ignition_year = time.strptime(ignition_date, "%Y-%m-%dT%H:%M:%S.%fZ").tm_year
    return main(
        geojson_boundary=geojson_boundary,
        ignition_year=ignition_year,
        fire_event_name=fire_event_name,
        affiliation=affiliation,
        cloud_static_io_client=cloud_static_io_client,
        logger=logger,
    )


def main(
    geojson_boundary: Any,
    ignition_year: int,
    fire_event_name: str,
    affiliation: str,
    cloud_static_io_client: CloudStaticIOClient,
    logger: Logger,
):
    try:
        rap_estimates = rap_get_biomass(
            geojson_boundary=geojson_boundary, ignition_year=ignition_year
        )

        # save the cog to the FTP server
        cloud_static_io_client.upload_rap_estimates(
            rap_estimates=rap_estimates,
            affiliation=affiliation,
            fire_event_name=fire_event_name,
        )
        logger.info(f"RAP estimates uploaded for {fire_event_name}")

        return JSONResponse(
            status_code=200,
            content={
                "message": f"RAP estimates uploaded for {fire_event_name}",
                "fire_event_name": fire_event_name,
            },
        )

    except Exception as e:
        sentry_sdk.capture_exception(e)
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
