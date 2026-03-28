import yfinance as yf
from backtest_vectorized import VectorizedEngine
import pandas as pd

def test_engine():
    print("Descargando datos...")
    df = yf.download("AAPL", period="1y", progress=False)
    if hasattr(df.columns, 'levels'):
        df.columns = df.columns.get_level_values(0)
    
    print("Ejecutando SMA Crossover Vectorizado...")
    pf = VectorizedEngine.run_sma_crossover(df, fast=20, slow=50)
    
    metrics = VectorizedEngine.extract_metrics(pf, df)
    print("Métricas obtenidas:")
    for k, v in metrics.items():
        print(f"  {k}: {v}")

    print("\nGenerando DF para UI...")
    res_df = VectorizedEngine.generate_ui_dataframe(pf, df)
    print(res_df.head(2))
    print(res_df.tail(2))
    print("\n✅ Prueba del VectorizedEngine exitosa.")

if __name__ == "__main__":
    test_engine()
