from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

model = ChatOpenAI()
# Define a template with multiple placeholders
template = PromptTemplate(
    input_variables=["name", "hobby"],
    template="Hello {name}! I heard you like {hobby}. Can you tell me more about it?"
)

# Format with different values
formatted_prompt = template.format(name="Anil", hobby="cricket")

print(formatted_prompt)

print("*************************************")

result = model.invoke(formatted_prompt)
print(result.content)