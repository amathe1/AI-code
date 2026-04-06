# 2️⃣ HumanMessage
# Represents a message from the user.
# Directly sends input to the AI.

from langchain.schema import HumanMessage

human_message = HumanMessage(content="What is the capital of India?")
print(human_message.content)
