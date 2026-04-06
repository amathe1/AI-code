from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema import AIMessage, HumanMessage

# Define a chat prompt template
chat_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful AI assistant."),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{question}")
])

# Format with chat history
formatted_chat = chat_prompt.format_messages(
    chat_history=[
        HumanMessage(content="What is the capital of India?"),
        AIMessage(content="The capital of India is New Delhi.")
    ],
    question="What is the population of above city?"
)

# Print formatted messages
for msg in formatted_chat:
    print(f"{msg.type}: {msg.content}")

#  Conclusion
# PromptTemplate allows structured dynamic prompt generation.
# It reduces redundancy and makes it easier to maintain prompts.
# Useful for LLM integration, chatbots, few-shot learning, and more.
