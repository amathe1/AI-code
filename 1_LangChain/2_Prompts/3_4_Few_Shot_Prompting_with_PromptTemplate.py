from langchain.prompts import FewShotPromptTemplate
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

model = ChatOpenAI()

# Define examples
examples = [
    {"input": "Explain AI", "output": "AI is the simulation of human intelligence in machines."},
    {"input": "Explain Blockchain", "output": "Blockchain is a decentralized digital ledger."}
]

# Define an example template
example_template = PromptTemplate(
    input_variables=["input", "output"],
    template="Q: {input}\nA: {output}"
)

# Create Few-Shot PromptTemplate
few_shot_prompt = FewShotPromptTemplate(
    examples=examples,
    example_prompt=example_template,
    prefix="Answer the following questions:",
    suffix="Q: {question}\nA:",
    input_variables=["question"]
)

# Format the prompt
formatted_prompt = few_shot_prompt.format(question="Explain Data Science")
print(formatted_prompt)

result = model.invoke(formatted_prompt)
print(result.content)
