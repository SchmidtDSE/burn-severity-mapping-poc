from fastapi import Depends, APIRouter, HTTPException
from fastapi.responses import JSONResponse
from logging import Logger
from typing import Any
from pydantic import BaseModel
import tempfile
import sentry_sdk
import json
import rioxarray as rxr
import xarray as xr
from ..dependencies import get_cloud_logger, get_cloud_static_io_client, init_sentry
from src.lib.query_sentinel import Sentinel2Client, NoFireBoundaryDetectedError
from src.util.cloud_static_io import CloudStaticIOClient

router = APIRouter()


class FloodFillRefinementPOSTBody(BaseModel):
    """
    Represents the request body for analyzing burn metrics.

    Attributes:
        geojson (str): The GeoJSON data in string format.
        fire_event_name (str): The name of the fire event.
        affiliation (str): The affiliation of the analysis.
    """

    geojson: Any
    fire_event_name: str
    affiliation: str


# TODO [#5]: Decide on / implement cloud tasks or other async batch
# This is a long running process, and users probably don't mind getting an email notification
# or something similar when the process is complete. Esp if the frontend remanins static.
@router.post(
    "/api/analyze/flood-fill-refinement",
    tags=["analysis"],
    description="Use seed points to refine a burn boundary.",
)
def analyze_spectral_burn_metrics(
    body: FloodFillRefinementPOSTBody,
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
    geojson_seed_points = json.loads(body.geojson)

    fire_event_name = body.fire_event_name
    affiliation = body.affiliation

    return main(
        geojson_seed_points,
        fire_event_name,
        affiliation,
        logger,
        cloud_static_io_client,
    )


def main(
    geojson_seed_points,
    fire_event_name,
    affiliation,
    logger,
    cloud_static_io_client,
):
    ## NOTE: derive_boundary is accepted for now to maintain compatibility with the frontend,
    ## but will shortly be a different endpoint

    logger.info(f"Received analyze-fire-event request for {fire_event_name}")

    try:
        # create a Sentinel2Client instance, without initializing, since we are
        # getting what we need from the cogs already generated
        geo_client = Sentinel2Client()

        ## TODO: Since we are running serverless, and don't have a live database, we are
        ## required to re-construct the metrics stack from the existing files, in the case
        ## where the user has identified fire boundaries from our intermediate rbr output.
        ## This is not ideal, but not sure there is a better solution without using something
        ## like redis or another live cache.
        metric_layers = []
        for metric_name in ["nbr_prefire", "nbr_postfire", "dnbr", "rdnbr", "rbr"]:
            with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmp:
                tmp_tiff = tmp.name
                cloud_static_io_client.download(
                    remote_path=f"public/{affiliation}/{fire_event_name}/{metric_name}.tif",
                    target_local_path=tmp_tiff,
                )

                metric_layer = rxr.open_rasterio(tmp_tiff)
                metric_layer = metric_layer.rename({"band": "burn_metric"})
                metric_layer["burn_metric"] = [metric_name]

                metric_layers.append(metric_layer)

        existing_metrics_stack = xr.concat(metric_layers, dim="band")
        geo_client.ingest_metrics_stack(existing_metrics_stack)

        logger.info(f"Loaded existing metrics stack for {fire_event_name}")

        # Use the seed points to perform flood fill refinement
        geo_client.derive_boundary_flood_fill(
            seed_points=geojson_seed_points,
            burn_metric="rbr",
            threshold=0.2,
        )

        # save the cog to the FTP server - this essentially overwrites
        # previous un-refined boundarie, but those are usually just imprecise
        # rectangles so this is fine
        cloud_static_io_client.update_metrics_stack(
            metrics_stack=geo_client.metrics_stack,
            affiliation=affiliation,
            fire_event_name=fire_event_name,
        )
        logger.info(f"Cogs updated for {fire_event_name}")

        return JSONResponse(
            status_code=200,
            content={
                "message": f"Cogs refined using flood-fill for {fire_event_name}",
                "fire_event_name": fire_event_name,
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
