from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage, AIMessage
from dotenv import load_dotenv

load_dotenv()

# Initialize Chat Model
chat_model = ChatOpenAI(model="gpt-3.5-turbo")

# Create a conversation with multiple message types
messages = [
    SystemMessage(content="You are a polite and knowledgeable assistant."),
    HumanMessage(content="Who won the Cricket World Cup in 2023?"),
    AIMessage(content="The Cricket World Cup 2023 was won by Australia."),
    HumanMessage(content="Who was the Player of the Tournament?")
]

# Get AI response
response = chat_model.invoke(messages)
print(response.content)
