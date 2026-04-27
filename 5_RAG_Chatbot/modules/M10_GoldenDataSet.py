import json
import os
from utils.config_loader import load_config

config = load_config()


def generate_golden_dataset():
    input_path = config["paths"]["chunks_json"]
    output_path = config["paths"]["golden_dataset"]

    with open(input_path, "r") as f:
        chunks = json.load(f)

    golden = {}

    for chunk in chunks[:50]:
        query = chunk["content"][:60]
        golden[query] = [chunk["content"]]

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(golden, f, indent=2)