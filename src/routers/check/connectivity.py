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
    """
    Check the connectivity to http://example.com.

    Args:
        logger (Logger): The logger object used for logging.

    Returns:
        Tuple[int, str]: A tuple containing the HTTP status code and a message.

    Raises:
        HTTPException: If there is an error during the connectivity check.
    """
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
