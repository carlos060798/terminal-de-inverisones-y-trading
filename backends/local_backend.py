"""Local Backend — Interface for local LLM engines (Ollama / Llama.cpp)."""
import requests
import json

DEFAULT_LOCAL_URL = "http://localhost:11434/v1/chat/completions"

def call(model, prompt, system="", max_tokens=1500, image_bytes=None, mime="image/png", tools=None):
    """
    Call a local LLM engine (defaulting to Ollama).
    """
    try:
        # Standard OpenAI-compatible format used by Ollama
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": max_tokens,
            "temperature": 0.3
        }
        
        # Tools are optional for local models (most don't support them well yet)
        if tools:
            # We skip tools for local fallback to ensure stability unless forced
            pass

        response = requests.post(DEFAULT_LOCAL_URL, json=payload, timeout=60)
        if response.status_code == 200:
            data = response.json()
            return data["choices"][0]["message"]["content"]
        else:
            return None
    except Exception:
        return None
