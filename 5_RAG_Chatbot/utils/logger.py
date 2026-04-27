import logging
import os

def setup_logger(log_file: str, level: str = "INFO"):
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    logger = logging.getLogger("rag_app")
    logger.setLevel(level)

    if not logger.handlers:
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s"
        )

        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger