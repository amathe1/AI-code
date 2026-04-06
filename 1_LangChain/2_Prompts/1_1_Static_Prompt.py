# 💡 Definition:
# A fixed, predefined prompt that does not change regardless of the input or context.

# 📌 Characteristics:

# The prompt remains the same every time.
# It does not adapt based on user inputs.
# Simple and good for structured tasks.

from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

model = ChatOpenAI()

prompt = PromptTemplate(
    input_variables=["topic"],
    template="Explain {topic} in simple terms."
)

formatted_prompt = prompt.format(topic="Agentic AI")
print(formatted_prompt)

print("++++++++++++++++++++++++++++++++++++++++")

result = model.invoke(formatted_prompt)
print(result.content)

# 📌 Use Cases:
# ✔️ Predefined tasks (e.g., FAQs, structured queries).
# ✔️ Consistent outputs in applications like chatbots.
# ✔️ When context-awareness is not needed.

# ❌ Limitations:

# Not flexible for dynamic user input.
# Cannot adapt to changing conversation flow.

# from langchain_openai import ChatOpenAI
# from dotenv import load_dotenv

# load_dotenv()

# model = ChatOpenAI(model='gpt-4')

# result = model.invoke("Explian langchain?")
# print(result.content)
