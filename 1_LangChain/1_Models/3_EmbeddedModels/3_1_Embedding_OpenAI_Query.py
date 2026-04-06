from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv

##https://platform.openai.com/docs/guides/embeddings

load_dotenv()
embedding = OpenAIEmbeddings(model="text-embedding-3-large")
result = embedding.embed_query("Delhi is the capital of India")

print(len(result))