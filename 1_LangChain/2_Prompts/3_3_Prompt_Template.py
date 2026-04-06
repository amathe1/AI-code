from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

# Define the prompt template
prompt = PromptTemplate(
    input_variables=["topic"],
    template="What are the key benefits of {topic}?"
)

# Initialize LLM (Use ChatOpenAI for chat models)
llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0.7)

# Generate response using formatted prompt
response = llm.invoke(prompt.format(topic="Machine Learning"))

# Print the generated response
print(response.content)

