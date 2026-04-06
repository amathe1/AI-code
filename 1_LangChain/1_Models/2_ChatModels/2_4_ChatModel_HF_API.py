import os
from langchain_huggingface import HuggingFaceEndpoint
from dotenv import load_dotenv

load_dotenv()
hf_token = os.getenv("HUGGINGFACEHUB_API_TOKEN")  # ✅ Correct key

if not hf_token:
    raise ValueError("Missing Hugging Face API token. Set 'HUGGINGFACEHUB_API_TOKEN' in .env.")

llm = HuggingFaceEndpoint(
    repo_id="mistralai/Mistral-7B-Instruct-v0.1",
    task="text-generation",
    huggingfacehub_api_token=hf_token,
)

prompt = "What is the capital of India?"
result = llm.invoke(prompt)
print(result)
