from fastapi import Depends, APIRouter, HTTPException
from ..dependencies import get_cloud_logger
from logging import Logger

import socket
import os

router = APIRouter()


@router.get("/api/check/dns", tags=["check"], summary="Check DNS resolution")
def check_dns(logger: Logger = Depends(get_cloud_logger)):
    """
    Check the DNS resolution for www.google.com.

    Args:
        logger (Logger): The logger object for logging messages.

    Returns:
        dict: A dictionary containing the resolved IP address.

    Raises:
        HTTPException: If there is an error during the DNS resolution.
    """
    try:
        TEST_DOMAIN = "www.google.com"
        ip_address = socket.gethostbyname(TEST_DOMAIN)
        logger.info(f"DNS check: Resolved {TEST_DOMAIN} to {ip_address}")
        return {"ip_address": ip_address}
    except Exception as e:
        logger.error(f"DNS check: Error {e}")
        raise HTTPException(status_code=400, detail=str(e))
