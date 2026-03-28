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

# Manual wrapper to handle @st.cache_resource only if in Streamlit
try:
    if st.runtime.exists():
        _get_client = st.cache_resource(_get_client)
except (ImportError, AttributeError):
    pass


def call(model: str, prompt: str, system: str = "", max_tokens: int = 4096,
         image_bytes: bytes = None, mime: str = None, tools: list = None) -> str:
    """Generate content using OpenAI chat completions, with optional tool calling."""
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

        # Tools configuration
        openai_tools = None
        if tools:
            # We already have the metadata in the right format (JSON Schema)
            # in agents.tools.TOOLS_METADATA
            from agents.tools import TOOLS_METADATA, TOOLS_MAP
            openai_tools = [{"type": "function", "function": t} for t in TOOLS_METADATA]

        # First Call
        kwargs = {}
        if openai_tools:
            kwargs["tools"] = openai_tools
            kwargs["tool_choice"] = "auto"
            
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.3,
            **kwargs
        )
        
        message = response.choices[0].message
        
        # Tool execution loop
        if message.tool_calls:
            messages.append(message)
            for tool_call in message.tool_calls:
                func_name = tool_call.function.name
                import json
                args = json.loads(tool_call.function.arguments)
                
                # Execute tool
                tool_func = TOOLS_MAP.get(func_name)
                if tool_func:
                    result = tool_func(**args)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": func_name,
                        "content": json.dumps(result),
                    })
            
            # Second Call to summarize results
            second_response = client.chat.completions.create(
                model=model,
                messages=messages,
            )
            return second_response.choices[0].message.content.strip()

        return message.content.strip() if message.content else ""
    except Exception as e:
        st.error(f"OpenAI Error: {e}")
        return ""
