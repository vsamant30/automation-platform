from datetime import datetime

from app.services.logger import logger


def run_sample_job():
    logger.info("========================================")
    logger.info("Job Started")
    logger.info("Executing Sample Automation Job")

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    result = f"Sample automation job completed at {current_time}"

    logger.info(result)
    logger.info("Job Completed Successfully")
    logger.info("========================================")

    return result