"""
Motor RAG local para indexar reportes y tesis usando ChromaDB.
Funciona 100% en local usando embeddings de sentence-transformers.
"""
import os
import sqlite3
from pathlib import Path

# Configuración de base de datos local
DB_DIR = Path(__file__).parent / "data" / "vector_db"
DB_DIR.mkdir(parents=True, exist_ok=True)

HAS_CHROMA = False
collection = None

try:
    import chromadb
    from chromadb.utils import embedding_functions
    
    # Inicializa cliente persistente (esto crea la carpeta la primera vez)
    vector_client = chromadb.PersistentClient(path=str(DB_DIR))
    
    # Modelo local ultraligero de HuggingFace para embeddings (descarga la primera vez ~100MB)
    sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )

    # Crea o carga la colección (tabla vectorial)
    collection = vector_client.get_or_create_collection(
        name="investment_thesis",
        embedding_function=sentence_transformer_ef
    )
    HAS_CHROMA = True
except ImportError:
    print("ChromaDB no está instalado. Ejecuta: pip install chromadb sentence-transformers")
except Exception as e:
    print(f"ChromaDB no disponible: {e}")
    HAS_CHROMA = False


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 150):
    """Divide un texto largo en pequeños chunks para el RAG."""
    chunks = []
    start = 0
    text_len = len(text)
    while start < text_len:
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


def ingest_document(ticker: str, source_name: str, text_content: str):
    """
    Convierte el texto en embeddings y lo guarda en ChromaDB.
    Se etiqueta con el ticker y la fuente original.
    """
    if not HAS_CHROMA or not text_content.strip():
        return False
        
    try:
        chunks = chunk_text(text_content)
        ids = [f"{ticker}_{source_name}_{i}" for i in range(len(chunks))]
        metadatas = [{"ticker": ticker.upper(), "source": source_name} for _ in chunks]
        
        # Insercion vectorial
        collection.add(
            documents=chunks,
            metadatas=metadatas,
            ids=ids
        )
        return True
    except Exception as e:
        print(f"Error ingestando {ticker}: {e}")
        return False


def query_knowledge(ticker: str, queryText: str, n_results: int = 3):
    """
    Busca en el historial de PDFs o tesis las partes más relevantes para una pregunta,
    filtrado estrictamente por el ticker.
    """
    if not HAS_CHROMA:
        return []
        
    try:
        results = collection.query(
            query_texts=[queryText],
            n_results=n_results,
            where={"ticker": ticker.upper()}
        )
        
        if results and results['documents'] and len(results['documents'][0]) > 0:
            # results['documents'][0] es la lista de textos devueltos para el primer queryText
            return results['documents'][0]
        return []
    except Exception as e:
        print(f"Error consultando vectorDB: {e}")
        return []

def get_memory_stats():
    """Retorna la cantidad de fragmentos almacenados."""
    if not HAS_CHROMA:
        return 0
    try:
        return collection.count()
    except:
        return 0
