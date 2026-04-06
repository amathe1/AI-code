from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain.schema.runnable import RunnableParallel

load_dotenv()

model = ChatOpenAI()

prompt_1 = PromptTemplate(
    template= "Generate a detailed report about a \n {topic}",
    input_variables=["topic"]
)

prompt_2 = PromptTemplate(
    template= "create a top 5 interview questions \n {topic}",
    input_variables=["topic"]
)

prompt_3 = PromptTemplate(
    template= " merge the provided detailed report and 5 interview questions into a single document \n notes -> {notes} and quiz -> {quiz}",
    input_variables=["notes", "quiz"]
)

parser = StrOutputParser()

parallel_chain = RunnableParallel({
    "notes": prompt_1 | model | parser,
    "quiz" : prompt_2 | model |parser
}
)

merge_chain = prompt_3 | model | parser

chain = parallel_chain | merge_chain


topic = """
Large Language Models (LLMs) are advanced artificial intelligence models designed to process and generate human-like text based on vast amounts of training data. These models, such as OpenAI’s GPT series, Google’s Gemini, and Meta’s LLaMA, use deep learning techniques, particularly transformer architectures, to understand and generate contextually relevant responses. LLMs power a wide range of applications, including chatbots, content creation, code generation, and research assistance. They excel in natural language understanding and generation, making them valuable for automating tasks that require linguistic intelligence. However, they also pose challenges, such as bias, misinformation, and high computational requirements, necessitating careful deployment and ethical considerations.
"""

result = chain.invoke({"topic":topic})
print(result)

chain.get_graph().print_ascii()