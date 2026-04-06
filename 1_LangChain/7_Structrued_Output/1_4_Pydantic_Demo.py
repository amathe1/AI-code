# 2. Pydantic Model Output (Strongly Typed)
# LangChain supports structured outputs via Pydantic models, allowing strict type enforcement.

from pydantic import BaseModel
from langchain_openai import ChatOpenAI

# Define a structured output model
class Review(BaseModel):
    key_themes: list[str]
    summary: str
    sentiment: str
    pros: list[str]
    cons: list[str]
    name: str

llm = ChatOpenAI(model="gpt-4")

structured_model = llm.with_structured_output(Review)

response = structured_model.invoke("Summarize this review: The phone is fast but expensive.")
print(response)
