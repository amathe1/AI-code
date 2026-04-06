from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser

load_dotenv()


model = ChatOpenAI()

parser = JsonOutputParser()

template = PromptTemplate(
    template='Give me 5 facts about {topic} \n {format_instruction}',
    input_variables=['topic'],
    partial_variables={'format_instruction': parser.get_format_instructions()}
)

chain = template | model | parser

result = chain.invoke({'topic':'Generative AI'})

print(result)

# 👉 In PromptTemplate, there are two types of variables:

# 1. input_variables
# Provided at runtime
# Example:
# chain.invoke({'topic': 'Generative AI'})

# 2. partial_variables
# Provided at template creation time
# Automatically injected
# User does NOT pass them later
# ✅ So this line means:

# 👉 “Before running the chain, always fill {format_instruction} 
# with this value.”