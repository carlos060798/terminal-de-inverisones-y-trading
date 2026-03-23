"""OpenRouter backend (OpenAI-compatible)."""
import base64
import re
import streamlit as st

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


def _get_secret(name: str) -> str:
    try:
        val = st.secrets.get(name)
        if val:
            return val
    except Exception:
        pass
    return __import__('os').environ.get(name, "")


@st.cache_resource
def _get_client():
    """Return an OpenRouter client or None."""
    if not HAS_OPENAI:
        return None
    api_key = _get_secret("OPENROUTER_API_KEY")
    if not api_key:
        return None
    try:
        return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
    except Exception:
        return None


def _clean_thinking(text: str) -> str:
    """Remove DeepSeek R1 thinking tags from output."""
    if "<think>" in text:
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    return text


def call(model: str, prompt: str, system: str = "", max_tokens: int = 4096,
         image_bytes: bytes = None, mime: str = None) -> str:
    """Generate content using OpenRouter."""
    client = _get_client()
    if client is None:
        return ""
    try:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})

        if image_bytes and mime:
            b64 = base64.b64encode(image_bytes).decode("utf-8")
            data_uri = f"data:{mime};base64,{b64}"
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_uri}},
                ],
            })
        else:
            messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.3,
        )
        text = response.choices[0].message.content.strip()

        if "deepseek" in model.lower():
            text = _clean_thinking(text)

        return text
    except Exception:
        return ""
