# 3. RunnableParallel
# RunnableParallel allows running multiple Runnable components in parallel, and it outputs a dictionary of results.

from langchain.schema.runnable import RunnableParallel, RunnableLambda, RunnablePassthrough

# Define multiple runnables
# uppercase_runnable = RunnableLambda(lambda x: x.upper())
# reverse_runnable = RunnableLambda(lambda x: x[::-1])

# Run them in parallel
parallel_runnable = RunnableParallel({
    "uppercase": RunnableLambda(lambda x: x.upper()),
    "reverse": RunnableLambda(lambda x: x[::-1]),
    "same data": RunnablePassthrough()
})

print(parallel_runnable.invoke("LangChain"))
# Output: {'uppercase': 'LANGCHAIN', 'reverse': 'niahCgnaL'}
