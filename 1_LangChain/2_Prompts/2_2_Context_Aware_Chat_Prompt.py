from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
load_dotenv()

chat_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a sales assistant."),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{question}")
])

formatted_messages = chat_prompt.format_messages(
    chat_history=[
        HumanMessage(content="Suggest a destination for a summer vacation."),
        AIMessage(content="How about Bali, Indonesia? It's great for summer!")
    ],
    question="What are the best activities to do there?"
)

llm = ChatOpenAI(model='gpt-4')
result = llm.invoke(formatted_messages)
print(result.content)
# Print the messages correctly
# for msg in formatted_messages:
#     print(f"{msg.type}: {msg.content}")

# 📌 Use Cases:
# ✔️ Conversational AI & Chatbots (context-aware prompts).
# ✔️ Adaptive Question Answering (modifies based on previous responses).
# ✔️ Personalized User Interactions (e.g., changing prompts based on user profiles).

# ❌ Limitations:

# More complex to implement than static prompting.
# Requires external logic (e.g., history tracking).

