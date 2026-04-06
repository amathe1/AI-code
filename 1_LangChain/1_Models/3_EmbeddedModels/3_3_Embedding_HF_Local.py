from langchain_huggingface import HuggingFaceEmbeddings

## https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2

embedding = HuggingFaceEmbeddings(model_name= "sentence-transformers/all-MiniLM-L6-v2")

text = "Delhi is the capital of India"

vector = embedding.embed_query(text)

print(len(vector))