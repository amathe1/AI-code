# 4. YAML Output
# Sometimes, YAML is preferred over JSON for readability.

from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

# Define the prompt template for YAML output
prompt = PromptTemplate.from_template(
    "List the key features of {product} in YAML format."
)

llm = ChatOpenAI(model="gpt-4")

# Generate YAML output
response = llm.invoke(prompt.format(product="iPhone 16"))
print(response)

