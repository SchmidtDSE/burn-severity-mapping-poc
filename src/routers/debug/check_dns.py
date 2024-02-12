from fastapi import Depends, APIRouter, HTTPException
from ..dependencies import get_cloud_logger
from logging import Logger

import socket
import os

router = APIRouter()

@router.get("/check-dns", tags=["debug"], summary="Check DNS resolution")
def check_dns(logger: Logger = Depends(get_cloud_logger)):
    try:
        TEST_DOMAIN = "www.google.com"
        ip_address = socket.gethostbyname(TEST_DOMAIN)
        logger.log_text(f"DNS check: Resolved {TEST_DOMAIN} to {ip_address}")
        return {"ip_address": ip_address}
    except Exception as e:
        logger.log_text(f"DNS check: Error {e}")
        raise HTTPException(status_code=400, detail=str(e))