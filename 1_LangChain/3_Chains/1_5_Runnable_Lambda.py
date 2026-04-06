# 1. RunnableLambda
# A RunnableLambda allows wrapping a simple Python function into a 
# LangChain-compatible Runnable.

from langchain.schema.runnable import RunnableLambda

# Define a simple function
def reverse_string(s: str) -> str:
    return s[::-1]

# Convert it into a Runnable
runnable = RunnableLambda(reverse_string)

# Execute
print(runnable.invoke("LangChain"))  # Output: "niahCgnaL"
