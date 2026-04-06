# 6. RunnableBranch
# A RunnableBranch allows conditional branching, executing different Runnable components based on a condition.

from langchain.schema.runnable import RunnableBranch,RunnableLambda

# Define different functions
uppercase = RunnableLambda(lambda x: x.upper())
reverse = RunnableLambda(lambda x: x[::-1])
default = RunnableLambda(lambda x: f"Unknown: {x}")

# Create a branch
branch = RunnableBranch(
    (lambda x: "uppercase" in x, uppercase),
    (lambda x: "reverse" in x, reverse),
    default  # Default branch
)

print(branch.invoke("uppercase me"))  # Output: "UPPERCASE ME"
print(branch.invoke("reverse me"))    # Output: "em esrever"
print(branch.invoke("something else"))  # Output: "Unknown: something else"


