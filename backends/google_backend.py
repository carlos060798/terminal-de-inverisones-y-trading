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

# Manual wrapper to handle @st.cache_resource only if in Streamlit
try:
    if st.runtime.exists():
        _get_client = st.cache_resource(_get_client)
except (ImportError, AttributeError):
    pass


def call(model: str, prompt: str, system: str = "", max_tokens: int = 4096,
         image_bytes: bytes = None, mime: str = None, tools: list = None) -> str:
    """Generate content using Google Gemini, with optional tool calling."""
    if not _get_client():
        return ""
    try:
        # Configuration for tools if provided
        generation_config = genai.GenerationConfig(
            temperature=0.3,
            max_output_tokens=max_tokens,
        )
        
        # Tools integration
        genai_tools = None
        if tools:
            from agents.tools import TOOLS_MAP
            # Simple conversion: Gemini can take Python functions directly 
            # or we can pass a list of functions if we import them.
            # But here we'll use the TOOLS_MAP to expose the functions.
            genai_tools = list(TOOLS_MAP.values())

        gm = genai.GenerativeModel(
            model_name=model,
            system_instruction=system if system else None,
            tools=genai_tools
        )

        if image_bytes and mime:
            image_part = genai.protos.Part(
                inline_data=genai.protos.Blob(mime_type=mime, data=image_bytes)
            )
            response = gm.generate_content([prompt, image_part], generation_config=generation_config)
        else:
            # Handle automatic tool execution if using chat session
            if tools:
                chat = gm.start_chat(enable_automatic_function_calling=True)
                response = chat.send_message(prompt, generation_config=generation_config)
            else:
                response = gm.generate_content(prompt, generation_config=generation_config)

        return response.text.strip() if response.text else ""
    except Exception as e:
        # Silently fail for multi-model chain to handle it
        return f"Error: {e}"
