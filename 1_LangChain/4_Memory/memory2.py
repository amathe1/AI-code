from langchain_openai import OpenAI
from dotenv import load_dotenv



load_dotenv()

# Define the model
llm = OpenAI()

print(llm.invoke("What is the capital of India ?"))