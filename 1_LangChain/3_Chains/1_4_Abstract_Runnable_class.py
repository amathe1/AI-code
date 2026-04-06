from abc import ABC, abstractmethod

# Abstract class
class Runnable(ABC):
    @abstractmethod
    def invoke(self, input_data):
        pass

# Child class: Prompt
class Prompt(Runnable):
    def invoke(self, input_data):
        return f"Processing prompt: {input_data}"

# Child class: LLM
class LLM(Runnable):
    def invoke(self, input_data):
        return f"Generating response for: {input_data}"

# Example usage
prompt = Prompt()
llm = LLM()

print(prompt.invoke("What is AI?"))
print(llm.invoke("Explain deep learning"))

# In LangChain, a Runnable is a fundamental interface that standardizes 
# the execution of various components (such as chains, LLMs, tools, 
# retrievers, etc.). It provides a structured way to define and execute 
# operations while enabling composability (i.e., connecting different 
# components together) and standardized execution.

# With Runnable, you can:

# Build custom components that process inputs and return outputs.
# Chain multiple Runnable components together.
# Execute tasks asynchronously or in parallel.
# Handle streaming of outputs.
# Implement branching and conditional execution in workflows.
