import os
import psutil


def report_load_metrics(logger):
    # Get system metrics
    load_avg = os.getloadavg()
    memory_info = psutil.virtual_memory()
    cpu_percent = psutil.cpu_percent(4)

    # Log system metrics
    logger.info(f"System Load Average: {load_avg}")
    logger.info(f"Memory Info: {memory_info}")
    logger.info(f"CPU Percent: {cpu_percent}")

    return load_avg, memory_info, cpu_percent
