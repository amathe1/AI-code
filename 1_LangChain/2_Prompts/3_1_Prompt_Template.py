# 🔹 What is a PromptTemplate?
# A PromptTemplate in LangChain is a structured way to create dynamic, reusable prompts. Instead of writing fixed prompts, PromptTemplate allows you to format them dynamically using placeholders ({variables}), making them adaptable for different inputs.

# 🔹 Why Use PromptTemplate?
# ✅ Reusability: Define a prompt once and use it with different inputs.
# ✅ Dynamic Formatting: Insert variables into the prompt dynamically.
# ✅ Maintainability: Keeps prompt structure separate from logic, making it easier to modify.
# ✅ Better Control: Helps structure prompts in an LLM-friendly way for better responses.

from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

model = ChatOpenAI()

# Define a template with placeholders
template = PromptTemplate(
    input_variables=["topic"],  # Placeholder variable
    template="Explain {topic} in simple terms."
)

# Format the prompt dynamically
formatted_prompt = template.format(topic="Quantum Computing")

# print(formatted_prompt)
result = model.invoke(formatted_prompt)
print(result.content)
