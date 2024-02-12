from fastapi import Depends, APIRouter, HTTPException
from fastapi.responses import JSONResponse
from logging import Logger
from typing import Any
from pydantic import BaseModel
import sentry_sdk
import json

from ..dependencies import get_cloud_logger, get_cloud_static_io_client, init_sentry
from src.lib.query_rap import (
    rap_get_biomass,
)
from src.util.cloud_static_io import CloudStaticIOClient

router = APIRouter()


class AnaylzeRapPOSTBody(BaseModel):
    geojson: Any
    ignition_date: str
    fire_event_name: str
    affiliation: str

@router.post("/api/fetch/rangeland_analysis_platform", tags=["fetch"], description="Fetch Rangeland Analysis Platform (RAP) biomass estimates"
def fetch_rangeland_analysis_platform(
    body: AnaylzeRapPOSTBody,
    cloud_static_io_client: CloudStaticIOClient = Depends(get_cloud_static_io_client),
    __sentry: None = Depends(init_sentry),
    logger: Logger = Depends(get_cloud_logger),
):
    boundary_geojson = json.loads(body.geojson)
    ignition_date = body.ignition_date
    fire_event_name = body.fire_event_name
    affiliation = body.affiliation

    sentry_sdk.set_context("analyze_rap", {"request": body})

    try:
        rap_estimates = rap_get_biomass(
            boundary_geojson=boundary_geojson,
            ignition_date=ignition_date
        )

        # save the cog to the FTP server
        cloud_static_io_client.upload_rap_estimates(
            rap_estimates=rap_estimates,
            affiliation=affiliation,
            fire_event_name=fire_event_name,
        )
        logger.log_text(f"RAP estimates uploaded for {fire_event_name}")

        return JSONResponse(
            status_code=200,
            content={
                "message": f"RAP estimates uploaded for {fire_event_name}",
                "fire_event_name": fire_event_name,
            },
        )

    except Exception as e:
        sentry_sdk.capture_exception(e)
        logger.log_text(f"Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

