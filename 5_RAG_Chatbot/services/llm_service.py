import os
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()
from utils.config_loader import load_config

config = load_config()

# Use chat model - 
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def generate_response(prompt: str) -> str:
    try:
        response = client.chat.completions.create(
            model=config["llm"]["model"],
            messages=[{"role": "user", "content": prompt}],
            temperature=config["llm"]["temperature"]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"LLM error: {e}"