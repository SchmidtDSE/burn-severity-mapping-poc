from fastapi import Depends, APIRouter, HTTPException
from fastapi.responses import JSONResponse
from logging import Logger
from typing import Any
from pydantic import BaseModel
import tempfile
import sentry_sdk
import json

from ..dependencies import get_cloud_logger, get_cloud_static_io_client, init_sentry
from src.lib.query_sentinel import Sentinel2Client, NoFireBoundaryDetectedError
from src.util.cloud_static_io import CloudStaticIOClient

router = APIRouter()


class AnaylzeBurnPOSTBody(BaseModel):
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
    derive_boundary: bool
    date_ranges: dict
    fire_event_name: str
    affiliation: str


# TODO [#5]: Decide on / implement cloud tasks or other async batch
# This is a long running process, and users probably don't mind getting an email notification
# or something similar when the process is complete. Esp if the frontend remanins static.
@router.post(
    "/api/analyze/spectral-burn-metrics",
    tags=["analysis"],
    description="Derive spectral burn metrics from satellite imagery within a boundary.",
)
def analyze_spectral_burn_metrics(
    body: AnaylzeBurnPOSTBody,
    cloud_static_io_client: CloudStaticIOClient = Depends(get_cloud_static_io_client),
    __sentry: None = Depends(init_sentry),
    logger: Logger = Depends(get_cloud_logger),
):
    """
    Analyzes spectral burn metrics for a given fire event.

    Args:
        body (AnaylzeBurnPOSTBody): The request body containing the necessary information for analysis.
        cloud_static_io_client (CloudStaticIOClient, optional): The client for interacting with the cloud storage service.  FastAPI handles this as a dependency injection.
        __sentry (None, optional): Sentry client, just needs to be initialized. FastAPI handles this as a dependency injection.
        logger (Logger, optional): Google cloud logger. FastAPI handles this as a dependency injection.

    Returns:
        JSONResponse: The response containing the analysis results and derived boundary, if applicable.
    """
    sentry_sdk.set_context("fire-event", {"request": body})
    geojson_boundary = json.loads(body.geojson)

    date_ranges = body.date_ranges
    fire_event_name = body.fire_event_name
    affiliation = body.affiliation
    derive_boundary = body.derive_boundary

    return main(
        geojson_boundary,
        date_ranges,
        fire_event_name,
        affiliation,
        derive_boundary,
        logger,
        cloud_static_io_client,
    )


def main(
    geojson_boundary,
    date_ranges,
    fire_event_name,
    affiliation,
    derive_boundary,
    logger,
    cloud_static_io_client,
):

    logger.info(f"Received analyze-fire-event request for {fire_event_name}")
    derived_boundary = None

    try:
        # create a Sentinel2Client instance
        geo_client = Sentinel2Client(geojson_boundary=geojson_boundary, buffer=0.1)

        # get imagery data before and after the fire
        geo_client.query_fire_event(
            prefire_date_range=date_ranges["prefire"],
            postfire_date_range=date_ranges["postfire"],
            from_bbox=True,
        )
        logger.info(f"Obtained imagery for {fire_event_name}")

        # calculate burn metrics
        geo_client.calc_burn_metrics()
        logger.info(f"Calculated burn metrics for {fire_event_name}")

        if derive_boundary:
            # Derive a boundary from the imagery
            # TODO [#16]: Derived boundary hardcoded for rbr / .025 threshold
            # Not sure yet but we will probably want to make this configurable
            geo_client.derive_boundary("rbr", 0.025)
            logger.info(f"Derived boundary for {fire_event_name}")

            # Upload the derived boundary
            with tempfile.NamedTemporaryFile(suffix=".geojson", delete=False) as tmp:
                tmp_geojson = tmp.name
                with open(tmp_geojson, "w") as f:
                    f.write(geo_client.geojson_boundary.to_json())

                cloud_static_io_client.upload(
                    source_local_path=tmp_geojson,
                    remote_path=f"public/{affiliation}/{fire_event_name}/boundary.geojson",
                )

            # Return the derived boundary
            derived_boundary = geo_client.geojson_boundary.to_json()

        # save the cog to the FTP server
        cloud_static_io_client.upload_fire_event(
            metrics_stack=geo_client.metrics_stack,
            affiliation=affiliation,
            fire_event_name=fire_event_name,
            prefire_date_range=date_ranges["prefire"],
            postfire_date_range=date_ranges["postfire"],
            derive_boundary=derive_boundary,
        )
        logger.info(f"Cogs uploaded for {fire_event_name}")

        return JSONResponse(
            status_code=200,
            content={
                "message": f"Cogs uploaded for {fire_event_name}",
                "fire_event_name": fire_event_name,
                "derived_boundary": derived_boundary,
            },
        )

    except NoFireBoundaryDetectedError as e:
        logger.info(f"No Fire Boundary Detected for fire event {fire_event_name}")
        return JSONResponse(
            status_code=204,
            content={
                "message": f"No Fire Boundary Detected for fire event {fire_event_name}"
            },
        )

    except Exception as e:
        sentry_sdk.capture_exception(e)
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
