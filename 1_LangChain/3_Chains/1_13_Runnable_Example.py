from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain.schema.runnable import RunnableSequence

load_dotenv()

model = ChatOpenAI()

prompt = PromptTemplate(
    template= "Generate 2 important topics about {topic}",
    input_variables=["topic"]
)

parser = StrOutputParser()

# chain = prompt | model | parser - LCEL

chain = RunnableSequence(prompt,model,parser)
result = chain.invoke({"topic":"Generative AI"})
print(result)