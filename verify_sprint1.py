from adapters.registry import get_adapter
from adapters.execution_engine import ExecutionEngine
import pandas as pd
import time

# Initialize engine
engine = ExecutionEngine()

print("--- VERIFICACIÓN SPRINT 1 ---")

# 1. Test SEC EDGAR (edgartools)
print("\n[1/3] Probando SEC EDGAR (edgartools)...")
t0 = time.perf_counter()
res_sec = engine.fetch_one("sec_edgar", ticker="AAPL", form_type="10-K", use_cache=False)
t1 = time.perf_counter()

if res_sec and res_sec.success:
    print(f"✅ SEC OK: Último 10-K de AAPL presentado el {res_sec.data.get('filed_at')}")
    print(f"   Latencia real: {t1-t0:.2f}s")
    if "balance_sheet" in res_sec.data:
        print(f"   Balance Sheet extraído: {len(res_sec.data['balance_sheet'])} filas")
else:
    print(f"❌ SEC FAILED: {res_sec.error if res_sec else 'No hay resultado'}")

# 2. Test Diskcache Persistence
print("\n[2/3] Probando Persistencia de Diskcache...")
t2 = time.perf_counter()
res_cached = engine.fetch_one("sec_edgar", ticker="AAPL")
t3 = time.perf_counter()
if res_cached and res_cached.success:
    print(f"✅ Cache OK: Datos recuperados en {t3-t2:.4f}s")
else:
    print("❌ Cache FAILED")

# 3. Test FRED (pandas_datareader)
print("\n[3/3] Probando FRED (pandas_datareader)...")
res_fred = engine.fetch_one("fred", series_id="GS10", use_cache=False)
if res_fred and res_fred.success:
    print(f"✅ FRED OK: {len(res_fred.data)} puntos extraídos para GS10 (10Y Yield)")
else:
    print(f"❌ FRED FAILED: {res_fred.error if res_fred else 'No hay resultado'}")

print("\n--- FIN DE VERIFICACIÓN ---")
engine.shutdown()
