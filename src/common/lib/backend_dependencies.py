from fastapi import Depends
from logging import Logger

from google.cloud import logging as google_logging
import sentry_sdk
from src.common.util.cloud_static_io import CloudStaticIOClient
from src.common.util.gcp_secrets import get_mapbox_secret as gcp_get_mapbox_secret
import os
import logging as python_logging


def get_cloud_logger():
    """
    Returns a Cloud Logging logger instance.

    Returns:
        google.cloud.logging.logger.Logger: The Cloud Logging logger instance.
    """
    logging_client = google_logging.Client(project="dse-nps")
    log_name = "burn-backend"
    logger = python_logging.getLogger(log_name)

    # Set the log level to DEBUG
    logger.setLevel(python_logging.INFO)

    # Attaches a Google Cloud Logging handler to the root logger
    handler = google_logging.handlers.CloudLoggingHandler(logging_client)
    python_logging.getLogger().addHandler(handler)

    return logger


def get_cloud_logger_debug():
    """
    Returns a Cloud Logging logger instance with DEBUG level.

    Returns:
        google.cloud.logging.logger.Logger: The Cloud Logging logger instance.
    """
    logging_client = google_logging.Client(project="dse-nps")
    log_name = "burn-backend"
    logger = python_logging.getLogger(log_name)

    # Set the log level to DEBUG
    logger.setLevel(python_logging.DEBUG)

    # Attaches a Google Cloud Logging handler to the root logger
    handler = google_logging.handlers.CloudLoggingHandler(logging_client)
    python_logging.getLogger().addHandler(handler)

    return logger


def get_cloud_static_io_client(logger: Logger = Depends(get_cloud_logger)):
    """
    Get an instance of CloudStaticIOClient.

    Args:
        logger (Logger): The logger instance to use for logging.

    Returns:
        CloudStaticIOClient: An instance of CloudStaticIOClient.
    """
    logger.info("Creating CloudStaticIOClient")
    s3_bucket_name = os.getenv("S3_BUCKET_NAME")
    return CloudStaticIOClient(s3_bucket_name, "s3", logger)


def get_manifest(
    cloud_static_io_client: CloudStaticIOClient = Depends(get_cloud_static_io_client),
    logger: Logger = Depends(get_cloud_logger),
):
    """
    Get the manifest from the cloud static IO client.

    Args:
        cloud_static_io_client (CloudStaticIOClient): The cloud static IO client instance, used to download the manifest from clouds storage.
        logger: The logger instance.

    Returns:
        dict: The manifest from the cloud storage.
    """
    logger.info("Getting manifest")
    manifest = cloud_static_io_client.get_manifest()
    return manifest


def init_sentry(logger: Logger = Depends(get_cloud_logger)):
    """
    Initializes the Sentry client.

    Args:
        logger (Logger): The logger object used for logging.

    Returns:
        None
    """
    logger.info("Initializing Sentry client")

    ## TODO [#28]: Move to sentry to environment variable if we keep sentry
    sentry_sdk.init(
        dsn="https://3660129e232b3c796208a5e46945d838@o4506701219364864.ingest.sentry.io/4506701221199872",
        # Set traces_sample_rate to 1.0 to capture 100%
        # of transactions for performance monitoring.
        traces_sample_rate=1.0,
        # Set profiles_sample_rate to 1.0 to profile 100%
        # of sampled transactions.
        # We recommend adjusting this value in production.
        profiles_sample_rate=1.0,
    )
    sentry_sdk.set_context("env", {"env": os.getenv("ENV")})
    logger.info("Sentry initialized")


def get_mapbox_secret():
    """
    Retrieves the Mapbox secret from GCP.

    Returns:
        str: The Mapbox secret.
    """
    return gcp_get_mapbox_secret()
