import os
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()
from utils.config_loader import load_config

config = load_config()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def generate_embedding(text: str):
    try:
        response = client.embeddings.create(
            model=config["embedding"]["model"],
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        raise Exception(f"Embedding error: {e}")