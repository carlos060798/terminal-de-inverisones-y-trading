"""
services/semantic_search.py — AI-Powered Semantic Search for Stocks
Uses ChromaDB and SentenceTransformers to index stock descriptions.
"""
import os
import chromadb
from chromadb.utils import embedding_functions
import yfinance as yf
import pandas as pd
from datetime import datetime

# Path for persistent storage
CHROMA_PATH = os.path.join("data", "chroma_db")
os.makedirs(CHROMA_PATH, exist_ok=True)

# Default embedding function
EMBED_MODEL = "all-MiniLM-L6-v2"
embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)

# Initialize Chroma Client
client = chromadb.PersistentClient(path=CHROMA_PATH)
collection = client.get_or_create_collection(
    name="stock_metadata", 
    embedding_function=embedding_func
)

def index_tickers(tickers, force=False):
    """
    Fetches descriptions and metadata for tickers and indexes them.
    """
    if not tickers:
        return
    
    # Filter out already indexed tickers unless force=True
    if not force:
        existing = collection.get(ids=tickers)
        existing_ids = set(existing['ids'])
        tickers = [t for t in tickers if t not in existing_ids]
    
    if not tickers:
        return

    documents = []
    metadatas = []
    ids = []
    
    for t in tickers:
        try:
            tk = yf.Ticker(t)
            info = tk.info
            summary = info.get("longBusinessSummary", "")
            if not summary:
                summary = f"{info.get('shortName', t)} in {info.get('sector', 'Unknown')} sector, {info.get('industry', 'Unknown')} industry."
            
            # Combine text for embedding
            full_text = f"{t} {info.get('shortName', '')}. {info.get('sector', '')} {info.get('industry', '')}. {summary}"
            
            documents.append(full_text)
            metadatas.append({
                "ticker": t,
                "name": info.get("shortName", ""),
                "sector": info.get("sector", ""),
                "industry": info.get("industry", ""),
                "market_cap": info.get("marketCap", 0)
            })
            ids.append(t)
        except Exception as e:
            print(f"[SEMANTIC] Error indexing {t}: {e}")
            continue
            
    if documents:
        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        print(f"[SEMANTIC] Indexed {len(documents)} new tickers.")

def search_stocks(query, n_results=12):
    """
    Searches for stocks matching the conceptual query.
    Returns list of metadata dicts.
    """
    try:
        results = collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        # Format results
        hits = []
        if results['metadatas'] and results['metadatas'][0]:
            for i in range(len(results['metadatas'][0])):
                meta = results['metadatas'][0][i]
                hits.append(meta)
        return hits
    except Exception as e:
        print(f"[SEMANTIC] Search error: {e}")
        return []

def get_indexed_count():
    return collection.count()
