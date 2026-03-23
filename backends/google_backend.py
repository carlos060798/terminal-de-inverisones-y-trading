"""Google Gemini backend."""
import streamlit as st

try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False


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
    """Configure the Gemini SDK and return True if successful."""
    if not HAS_GEMINI:
        return False
    api_key = _get_secret("GEMINI_API_KEY")
    if not api_key:
        return False
    try:
        genai.configure(api_key=api_key)
        return True
    except Exception:
        return False


def call(model: str, prompt: str, system: str = "", max_tokens: int = 4096,
         image_bytes: bytes = None, mime: str = None) -> str:
    """Generate content using Google Gemini."""
    if not _get_client():
        return ""
    try:
        gm = genai.GenerativeModel(model)
        full_prompt = f"{system}\n\n{prompt}" if system else prompt

        if image_bytes and mime:
            image_part = genai.protos.Part(
                inline_data=genai.protos.Blob(mime_type=mime, data=image_bytes)
            )
            response = gm.generate_content(
                [full_prompt, image_part],
                generation_config=genai.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=max_tokens,
                ),
            )
        else:
            response = gm.generate_content(
                full_prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=max_tokens,
                ),
            )

        return response.text.strip() if response.text else ""
    except Exception:
        return ""
