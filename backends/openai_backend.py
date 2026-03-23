"""OpenAI backend."""
import base64
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
    """Return an OpenAI client or None."""
    if not HAS_OPENAI:
        return None
    api_key = _get_secret("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        return OpenAI(api_key=api_key)
    except Exception:
        return None


def call(model: str, prompt: str, system: str = "", max_tokens: int = 4096,
         image_bytes: bytes = None, mime: str = None) -> str:
    """Generate content using OpenAI chat completions."""
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
        return response.choices[0].message.content.strip()
    except Exception:
        return ""
