# Message Placeholder in LangChain
# 🔹 What is a Message Placeholder?
# A Message Placeholder in LangChain is a special type of placeholder used in prompt templates to dynamically inject messages (e.g., user input, AI responses, system instructions) when executing a prompt.

# It allows structured conversation handling by keeping different message types (SystemMessage, HumanMessage, AIMessage) and dynamically inserting them into prompts.

# 🔹 Why Use Message Placeholders?
# ✅ Helps in structuring multi-turn conversations.
# ✅ Allows dynamic message injection into templates.
# ✅ Supports memory mechanisms for conversation history.

from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema import SystemMessage, HumanMessage, AIMessage

# Define a prompt template with a message placeholder
prompt = ChatPromptTemplate.from_messages([
    SystemMessage(content="You are an AI assistant that answers questions."),
    MessagesPlaceholder(variable_name="chat_history"),  # This is the placeholder
    HumanMessage(content="{question}")  # Dynamic user input
])

# Example conversation history
chat_history = [
    HumanMessage(content="Who won the 2011 Cricket World Cup?"),
    AIMessage(content="India won the 2011 Cricket World Cup."),
]

# Format the prompt with dynamic input
formatted_prompt = prompt.format_messages(
    chat_history=chat_history,  # Inject past messages
    question="Who was the captain of the winning team?"
)

# Output formatted messages
for message in formatted_prompt:
    print(f"{message.type}: {message.content}")


# 🔹 How Message Placeholders Work?
# MessagesPlaceholder(variable_name="chat_history")
# Acts as a dynamic placeholder for inserting previous messages.
# Stores multi-turn conversation history dynamically.
# Helps in creating context-aware AI responses.

# 🔹 Where are Message Placeholders Used?
# 🔹 Conversation Memory (e.g., ConversationBufferMemory, ConversationSummaryMemory).
# 🔹 Custom Chat Bots that maintain message history.
# 🔹 Multi-turn LLM-based applications (e.g., RAG, customer support bots).

