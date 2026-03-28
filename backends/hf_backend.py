"""Hugging Face Inference backend."""
import base64
import streamlit as st

try:
    from huggingface_hub import InferenceClient
    HAS_HF = True
except ImportError:
    HAS_HF = False


def _get_secret(name: str) -> str:
    try:
        val = st.secrets.get(name)
        if val:
            return val
    except Exception:
        pass
    return __import__('os').environ.get(name, "")


def _get_client():
    """Return a HuggingFace InferenceClient or None."""
    if not HAS_HF:
        return None
    token = _get_secret("HF_TOKEN")
    if not token:
        return None
    try:
        return InferenceClient(token=token)
    except Exception:
        return None

# Manual wrapper for Streamlit cache
try:
    if st.runtime.exists():
        _get_client = st.cache_resource(_get_client)
except (ImportError, AttributeError):
    pass


def call(model: str, prompt: str, system: str = "", max_tokens: int = 4096,
         image_bytes: bytes = None, mime: str = None, tools: list = None) -> str:
    """Generate content using HuggingFace Inference API. Tools not natively supported here yet."""
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

        response = client.chat_completion(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error: {e}"


def sentiment(headlines: list) -> list[dict]:
    """Run FinBERT sentiment classification on a list of headlines.

    Returns a list of {"label": str, "score": float} dicts.
    """
    client = _get_client()
    if client is None:
        return []
    results = []
    for headline in headlines:
        try:
            output = client.text_classification(
                model="ProsusAI/finbert",
                text=headline,
            )
            if output:
                top = output[0]
                results.append({"label": top.label, "score": round(top.score, 4)})
            else:
                results.append({"label": "neutral", "score": 0.0})
        except Exception:
            results.append({"label": "neutral", "score": 0.0})
    return results


def table_qa(table: dict, query: str) -> str:
    """Answer a question about a table using TAPAS.

    Args:
        table: Dict with "header" (list[str]) and "rows" (list[list[str]]) keys.
        query: Natural language question about the table.

    Returns:
        Answer string or empty string on failure.
    """
    client = _get_client()
    if client is None:
        return ""
    try:
        result = client.table_question_answering(
            model="google/tapas-base-finetuned-wtq",
            table=table,
            query=query,
        )
        if hasattr(result, "answer"):
            return result.answer
        return str(result) if result else ""
    except Exception:
        return ""
