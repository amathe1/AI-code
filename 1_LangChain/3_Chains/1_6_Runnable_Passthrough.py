# 2. RunnablePassthrough
# A RunnablePassthrough is a basic implementation that returns 
# the input as output without any modifications. It is useful when 
# integrating components that do not require processing at a certain stage.

from langchain.schema.runnable import RunnablePassthrough

runnable = RunnablePassthrough()
print(runnable.invoke("Hello, World!"))  # Output: "Hello, World!"

