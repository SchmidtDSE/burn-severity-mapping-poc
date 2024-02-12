from fastapi import Depends, APIRouter, HTTPException
from fastapi.responses import JSONResponse
from logging import Logger
from typing import Any
from pydantic import BaseModel
import tempfile
import sentry_sdk
import json

from ..dependencies import get_cloud_logger, get_cloud_static_io_client, init_sentry
from src.lib.query_sentinel import Sentinel2Client
from src.util.cloud_static_io import CloudStaticIOClient

router = APIRouter()

class AnaylzeBurnPOSTBody(BaseModel):
    geojson: Any
    derive_boundary: bool
    date_ranges: dict
    fire_event_name: str
    affiliation: str


# TODO [#5]: Decide on / implement cloud tasks or other async batch
# This is a long running process, and users probably don't mind getting an email notification
# or something similar when the process is complete. Esp if the frontend remanins static.
@router.post("/api/query-satellite/analyze-fire-event", tags=["analysis"], description="Analyze a fire event")
def analyze_burn(
    body: AnaylzeBurnPOSTBody,
    cloud_static_io_client: CloudStaticIOClient = Depends(get_cloud_static_io_client),
    __sentry = Depends(init_sentry),
    logger: Logger = Depends(get_cloud_logger),
):
    geojson_boundary = json.loads(body.geojson)

    date_ranges = body.date_ranges
    fire_event_name = body.fire_event_name
    affiliation = body.affiliation
    derive_boundary = body.derive_boundary
    derived_boundary = None

    sentry_sdk.set_context("fire-event", {"request": body})
    logger.log_text(f"Received analyze-fire-event request for {fire_event_name}")

    try:
        # create a Sentinel2Client instance
        geo_client = Sentinel2Client(geojson_boundary=geojson_boundary, buffer=0.1)

        # get imagery data before and after the fire
        geo_client.query_fire_event(
            prefire_date_range=date_ranges["prefire"],
            postfire_date_range=date_ranges["postfire"],
            from_bbox=True,
        )
        logger.log_text(f"Obtained imagery for {fire_event_name}")

        # calculate burn metrics
        geo_client.calc_burn_metrics()
        logger.log_text(f"Calculated burn metrics for {fire_event_name}")

        if derive_boundary:
            # Derive a boundary from the imagery
            # TODO [#16]: Derived boundary hardcoded for rbr / .025 threshold
            # Not sure yet but we will probably want to make this configurable
            geo_client.derive_boundary("rbr", 0.025)
            logger.log_text(f"Derived boundary for {fire_event_name}")

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
        logger.log_text(f"Cogs uploaded for {fire_event_name}")

        return JSONResponse(
            status_code=200,
            content={
                "message": f"Cogs uploaded for {fire_event_name}",
                "fire_event_name": fire_event_name,
                "derived_boundary": derived_boundary,
            },
        )
    
    except Exception as e:
        sentry_sdk.capture_exception(e)
        logger.log_text(f"Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))