# 5. CSV Output
# For structured tabular data, CSV format can be requested.

from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Define LLM with a specific model
llm = ChatOpenAI(model="gpt-4")

# Define the prompt template correctly
prompt = PromptTemplate.from_template(
    "Provide a CSV list of the best programming languages with their main use case."
)

# Format the prompt before passing it to invoke()
formatted_prompt = prompt.format()

# Get response from LLM
response = llm.invoke(formatted_prompt)

# Print the generated CSV output
print(response)

