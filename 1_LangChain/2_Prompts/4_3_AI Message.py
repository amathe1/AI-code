# 3️⃣ AIMessage
# Represents a response from the AI.
# Used for storing AI-generated responses.

from langchain.schema import AIMessage

ai_message = AIMessage(content="The capital of India is New Delhi.")
print(ai_message.content)
