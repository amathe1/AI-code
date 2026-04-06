# 4. RunnableMap
# A RunnableMap works like RunnableParallel but applies a single Runnable to each element of an input list.

from langchain.schema.runnable import RunnableLambda

# Define a RunnableLambda that applies upper() to each element in a list
uppercase_runnable = RunnableLambda(lambda x: [word.upper() for word in x])

# Invoke with a list of strings
print(uppercase_runnable.invoke(["hello", "world"]))  
# Output: ['HELLO', 'WORLD']


