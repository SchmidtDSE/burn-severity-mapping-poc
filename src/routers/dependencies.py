from fastapi import Depends
from logging import Logger

from google.cloud import logging
import sentry_sdk
from src.util.cloud_static_io import CloudStaticIOClient
from src.util.gcp_secrets import get_mapbox_secret as gcp_get_mapbox_secret
import os

def get_cloud_logger():
    logging_client = logging.Client(project="dse-nps")
    log_name = "burn-backend"
    logger = logging_client.logger(log_name)

    return logger

def get_cloud_static_io_client(logger: Logger = Depends(get_cloud_logger)):
    logger.log_text("Creating CloudStaticIOClient")
    return CloudStaticIOClient('burn-severity-backend', "s3")

def get_manifest(
        cloud_static_io_client: CloudStaticIOClient = Depends(get_cloud_static_io_client),
        logger: Logger = Depends(get_cloud_logger)
):
    logger.log_text("Getting manifest")
    manifest = cloud_static_io_client.get_manifest()
    return manifest

def init_sentry(
        logger: Logger = Depends(get_cloud_logger)
):
    logger.log_text("Initializing Sentry client")

    ## TODO [$65cba09842ca860008e06391]: Move to sentry to environment variable if we keep sentry
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
    sentry_sdk.set_context("env", {"env": os.getenv('ENV')})
    logger.log_text("Sentry initialized")

def get_mapbox_secret():
    return gcp_get_mapbox_secret()