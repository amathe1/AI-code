from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

load_dotenv()

model = ChatOpenAI()

prompt_1 = PromptTemplate(
    template= "Generate a detailed report about a {topic}",
    input_variables=["topic"]
)

prompt_2 = PromptTemplate(
    template= "create a top 5 interview questions {topic}",
    input_variables=["topic"]
)

parser = StrOutputParser()

chain = prompt_1 | model | parser | prompt_2 | model | parser

result = chain.invoke({"topic":"challenges with deep neural network"})

print(result)

chain.get_graph().print_ascii()