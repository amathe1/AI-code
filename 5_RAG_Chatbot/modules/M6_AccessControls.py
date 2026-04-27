from utils.config_loader import load_config
from utils.logger import setup_logger

config = load_config()
logger = setup_logger(config["paths"]["logs"])

def validate_user(username: str = None, password: str = None) -> bool:
    if not config["access_control"]["enabled"]:
        return True

    if not username or not password:
        return False

    users = config["access_control"]["users"]

    for user in users:
        if user["username"] == username and user["password"] == password:
            return True

    logger.warning("Unauthorized access attempt")
    return False