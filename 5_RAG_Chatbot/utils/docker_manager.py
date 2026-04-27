import subprocess
import time
from utils.config_loader import load_config

config = load_config()

def start_docker_services():
    if not config["docker"]["auto_start"]:
        return

    try:
        print("🚀 Starting Docker containers...")
        subprocess.run(["docker-compose", "up", "-d"], check=True)

        wait_for_services()

    except Exception as e:
        print(f"Docker startup failed: {e}")


def wait_for_services():
    wait_time = config["docker"]["wait_time_seconds"]
    print(f"⏳ Waiting {wait_time}s for services...")
    time.sleep(wait_time)