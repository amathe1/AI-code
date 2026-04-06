from langchain_huggingface import HuggingFaceEmbeddings

## https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2

embedding = HuggingFaceEmbeddings(model_name= "sentence-transformers/all-MiniLM-L6-v2")

documents = [
    "Delhi is the capital of India",
    "Hyderabad is the capital of Telangana",
    "Paris is the capital of France"
]

vector = embedding.embed_documents(documents)

print(str(vector))