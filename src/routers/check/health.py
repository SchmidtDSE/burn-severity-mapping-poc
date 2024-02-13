from fastapi import Depends, APIRouter
from ..dependencies import get_cloud_logger
from logging import Logger

router = APIRouter()


@router.get("/api/check/health", tags=["check"], description="Health check endpoint")
def health(logger: Logger = Depends(get_cloud_logger)):
    logger.log_text("Health check endpoint called")
    return "Alive", 200
