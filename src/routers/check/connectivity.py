from fastapi import Depends, APIRouter, HTTPException
from ..dependencies import get_cloud_logger
from logging import Logger

import requests

router = APIRouter()


@router.get(
    "/api/check/connectivity",
    tags=["check"],
    description="Check connectivity to example.com",
)
def check_connectivity(logger: Logger = Depends(get_cloud_logger)):
    try:
        response = requests.get("http://example.com")
        logger.log_text(
            f"Connectivity check: Got response {response.status_code} from http://example.com"
        )
        return (
            200,
            f"Connectivity check: Got response {response.status_code} from http://example.com",
        )

    except Exception as e:
        logger.log_text(f"Connectivity check: Error {e}")
        raise HTTPException(status_code=400, detail=str(e))
