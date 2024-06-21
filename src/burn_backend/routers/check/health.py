from fastapi import Depends, APIRouter
from ..dependencies import get_cloud_logger
from logging import Logger

router = APIRouter()


@router.get("/api/check/health", tags=["check"], description="Health check endpoint")
def health(logger: Logger = Depends(get_cloud_logger)):
    """
    Ping pong!

    Args:
        logger (Logger): The logger object for logging messages.

    Returns:
        Tuple[str, int]: A tuple containing the response message and status code.
    """
    logger.info("Health check endpoint called")
    return "Alive", 200
