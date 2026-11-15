
import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv(override=True)

def get_llm():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is missing from .env")

    model_name = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

    print("Groq model selected:", model_name)

    return ChatGroq(
        model=model_name,
        temperature=0.1,
        api_key=api_key,
    )
