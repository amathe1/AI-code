# In LangChain, messages are structured objects that 
# allow conversations to be properly formatted for 
# chat-based models. These messages help in 
# multi-turn conversations and defining roles for the 
# AI and user.

# 1️⃣ SystemMessage
# Defines rules, context, or instructions for the AI.
# Helps guide the behavior of the AI before it starts 
# responding.

from langchain.schema import SystemMessage

system_message = SystemMessage(content="You are a helpful AI assistant.")
print(system_message.content)
