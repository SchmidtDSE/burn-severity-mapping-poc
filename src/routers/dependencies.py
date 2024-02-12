from google.cloud import logging

def get_cloud_logger():
    logging_client = logging.Client(project="dse-nps")
    log_name = "burn-backend"
    logger = logging_client.logger(log_name)

    return logger
