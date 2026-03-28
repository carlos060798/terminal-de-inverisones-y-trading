import os
import toml
from pathlib import Path

# Manual load of Streamlit secrets for standalone testing
secrets_path = Path(".streamlit/secrets.toml")
if secrets_path.exists():
    secrets = toml.load(secrets_path)
    for key, val in secrets.items():
        if isinstance(val, str):
            os.environ[key] = val

import ai_router
import time

print("--- VERIFICACIÓN SPRINT 2 ---")

# 1. Test Function Calling in Chat
# We use a ticker that is likely to have data in the cache from Sprint 1 (AAPL)
print("\n[1/2] Probando Chat con Herramientas (Function Calling)...")
prompt = "Calcula el valor intrínseco de AAPL y dime su Altman Z-Score."
try:
    response = ai_router.generate(prompt)
    print(f"Respuesta de la IA:\n{response}")
except Exception as e:
    print(f"❌ Error en Chat: {e}")

# 2. Test LangGraph Agent
print("\n[2/2] Probando Agente Autónomo (LangGraph)...")
try:
    thesis = ai_router.run_agentic_analysis("NVDA", "Analiza Nvidia en profundidad.")
    print(f"Tesis del Agente:\n{thesis}")
except Exception as e:
    print(f"❌ Error en Agente: {e}")

print("\n--- FIN DE VERIFICACIÓN ---")
