from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv

##https://platform.openai.com/docs/guides/embeddings

load_dotenv()

documents = [
    "Delhi is the capital of India",
    "Hyderabad is the capital of Telangana",
    "Paris is the capital of France"
]
embedding = OpenAIEmbeddings(model="text-embedding-3-large", dimensions=10)
result = embedding.embed_documents(documents)

print(str(result))