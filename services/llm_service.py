import os
import re
import time
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv(override=True)


class RetryChatGroq:
    """Wrapper around ChatGroq that intercepts 429 RateLimitErrors and sleeps/retries automatically."""

    def __init__(self, chat_groq):
        self._llm = chat_groq

    def invoke(self, *args, **kwargs):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                return self._llm.invoke(*args, **kwargs)
            except Exception as exc:
                err_str = str(exc)
                is_rate_limit = (
                    "429" in err_str
                    or "Rate limit" in err_str
                    or "rate_limit_exceeded" in err_str
                    or "tokens per minute" in err_str
                )
                if is_rate_limit and attempt < max_retries - 1:
                    match = re.search(r"try again in ([\d\.]+)s", err_str)
                    wait_time = float(match.group(1)) + 1.2 if match else 2.5 * (attempt + 1)
                    print(f"Groq 429 rate limit hit. Waiting {wait_time:.2f}s before automatic retry (attempt {attempt + 1}/{max_retries})...")
                    time.sleep(wait_time)
                else:
                    raise
        return self._llm.invoke(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._llm, name)


def get_llm():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is missing from .env")

    model_name = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    print("Groq model selected:", model_name)

    base_llm = ChatGroq(
        model=model_name,
        temperature=0.1,
        api_key=api_key,
        max_retries=3,
    )
    return RetryChatGroq(base_llm)
