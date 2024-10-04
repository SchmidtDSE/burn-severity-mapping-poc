from fastapi import Depends, APIRouter
from src.common.lib.backend_dependencies import get_cloud_logger
from logging import Logger

router = APIRouter()


@router.get("/api/check/logs", tags=["check"], description="Check logging")
def check_logs(logger: Logger = Depends(get_cloud_logger)):
    logger.debug("Debug log")
    logger.info("Info log")
    logger.warning("Warning log")
    logger.error("Error log")
    logger.critical("Critical log")
    return 200
