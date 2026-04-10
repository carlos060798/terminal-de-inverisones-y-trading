import os
import streamlit as st
import yt_dlp
import whisper
import torch

# Directory to save audio
CACHE_DIR = "d:/dasboard/cache/earnings"
os.makedirs(CACHE_DIR, exist_ok=True)

@st.cache_resource
def load_whisper_model(model_name="small"):
    """Loads Whisper model (cached in memory)."""
    device = "cuda" if torch.cuda.is_available() else "cpu"
    return whisper.load_model(model_name, device=device)

def download_audio(url: str, filename: str):
    """Downloads audio from YouTube or IR link."""
    output_path = os.path.join(CACHE_DIR, f"{filename}.mp3")
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': os.path.join(CACHE_DIR, f"{filename}.%(ext)s"),
        'quiet': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    
    return output_path

def transcribe_earnings(audio_path: str):
    """Transcribes audio using local Whisper model."""
    model = load_whisper_model()
    result = model.transcribe(audio_path)
    return result["text"]

def analyze_earnings_sentiment(text: str):
    """
    Placeholder for FinBERT analysis.
    In a real scenario, we'd chunk the text and run sentiment_service.
    """
    from services import sentiment_service
    # Simple chunking logic
    chunks = [text[i:i+500] for i in range(0, len(text), 500)]
    scores = []
    for chunk in chunks[:10]: # Limit for demo
        sent = sentiment_service.analyze_sentiment_finbert(chunk)
        scores.append(sent)
    
    return scores
