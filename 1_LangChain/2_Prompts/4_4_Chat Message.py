# 4️⃣ ChatMessage
# A generic message where you can specify the role ("system", "user", "assistant", etc.).
# Useful for creating custom message types.

from langchain.schema import ChatMessage

chat_message = ChatMessage(role="mentor", content="Always double-check your AI-generated answers.")
print(chat_message.content)
