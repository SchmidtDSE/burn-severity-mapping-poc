from fastapi import Depends, APIRouter
from ..dependencies import get_cloud_logger
from logging import Logger

router = APIRouter()

@router.get("/api/check/sentry-error", tags=["check"], summary="Trigger a division by zero error for Sentry to catch.")
async def trigger_error(logger: Logger = Depends(get_cloud_logger)):
    logger.log_text("Triggering a division by zero error for Sentry to catch.")
    __division_by_zero = 1 / 0