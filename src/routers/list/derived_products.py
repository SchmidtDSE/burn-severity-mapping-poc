from fastapi import Depends, APIRouter, HTTPException
from fastapi.responses import JSONResponse
from logging import Logger
from typing import Any
from pydantic import BaseModel
import sentry_sdk

from ..dependencies import get_cloud_logger, get_cloud_static_io_client, init_sentry
from src.util.cloud_static_io import CloudStaticIOClient

router = APIRouter()


class GetDerivedProductsPOSTBody(BaseModel):
    """
    Represents the request body for the GetDerivedProducts endpoint, which
    essentially lists the files available for download for a given fire event.

    Attributes:
        fire_event_name (str): The name of the fire event.
        affiliation (str): The affiliation of the derived products.
    """

    fire_event_name: str
    affiliation: str


@router.post(
    "/api/list/derived-products",
    tags=["list"],
    description="List derived products of a fiven fire event / affiliation combination.",
)
async def list_derived_products(
    body: GetDerivedProductsPOSTBody,
    cloud_static_io_client: CloudStaticIOClient = Depends(get_cloud_static_io_client),
    __sentry: None = Depends(init_sentry),
    logger: Logger = Depends(get_cloud_logger),
):
    """
    Retrieves a list of derived products within a given fire event and affiliation. This hits our own
    backend service to list the available derived products.

    Args:
        body (GetDerivedProductsPOSTBody): The request body containing the parameters.
        cloud_static_io_client (CloudStaticIOClient): The client for interacting with the cloud static IO.
        __sentry (None): The sentry dependency.
        logger (Logger): The logger for logging messages.

    Returns:
        JSONResponse: The response containing the derived products.

    Raises:
        HTTPException: If an error occurs during the retrieval of derived products.
    """
    fire_event_name = body.fire_event_name
    affiliation = body.affiliation

    sentry_sdk.set_context(
        "get_derived_products",
        {"fire_event_name": fire_event_name, "affiliation": affiliation},
    )

    try:
        derived_products = cloud_static_io_client.get_derived_products(
            affiliation=affiliation, fire_event_name=fire_event_name
        )
        return JSONResponse(status_code=200, content=derived_products)

    except Exception as e:
        sentry_sdk.capture_exception(e)
        logger.log_text(f"Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
