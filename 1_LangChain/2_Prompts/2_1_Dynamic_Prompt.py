# 💡 Definition:
# A flexible and adaptive prompt that changes based on user input, external data, or context.

# 📌 Characteristics:
# - The prompt adjusts dynamically.
# - Uses real-time variables (user input, API results, etc.).
# - Good for personalized, multi-step conversations.

import random
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv  # ✅ Updated import (newer LangChain versions)

load_dotenv()
model = ChatOpenAI()
# Define multiple prompt templates
templates = [
    "Summarize {topic} in one paragraph.",
    "Give a brief explanation of {topic}.",
    "Explain {topic} as if I am a house wife."
]

# Randomly select a template
selected_template = random.choice(templates)
print("🔹 Selected Template:", selected_template)

# Create a PromptTemplate object
prompt = PromptTemplate(
    input_variables=["topic"],
    template=selected_template
)

# Format the prompt with a specific topic
formatted_prompt = prompt.format(topic="Artificial Intelligence")
print("✅ Formatted Prompt:", formatted_prompt)

result = model.invoke(formatted_prompt)
print("✅ Result:", result.content)
