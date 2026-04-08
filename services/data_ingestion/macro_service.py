import wbgapi as wb
import pandas as pd
import database as db
from datetime import datetime

# Definición de indicadores clave del Banco Mundial
# NY.GDP.MKTP.KD.ZG: Crecimiento del PIB (%)
# FP.CPI.TOTL.ZG: Inflación, precios al consumidor (% anual)
# SL.UEM.TOTL.ZS: Desempleo, total (% de la población activa)
INDICATORS = {
    'NY.GDP.MKTP.KD.ZG': 'GDP Growth (%)',
    'FP.CPI.TOTL.ZG': 'Inflation (%)',
    'SL.UEM.TOTL.ZS': 'Unemployment (%)'
}

COUNTRIES = ['USA', 'CHN', 'JPN', 'DEU', 'GBR', 'FRA', 'IND', 'MEX', 'BRA', 'EUU']

def sync_worldbank_macro():
    """
    Sincroniza datos macroeconómicos globales del Banco Mundial.
    Se ejecuta típicamente una vez al mes ya que estos datos son anuales/trimestrales.
    """
    try:
        current_year = datetime.now().year
        # Obtener los últimos 5 años para tener una serie temporal básica
        years = range(current_year - 5, current_year)
        
        print(f"[MACRO SERVICE] Descargando indicadores {list(INDICATORS.values())} para {len(COUNTRIES)} países...")
        
        # WB data returns a multi-index or flattened dataframe depending on params
        for ind_id, ind_name in INDICATORS.items():
            df = wb.data.DataFrame(ind_id, COUNTRIES, time=years, labels=True)
            
            # El DataFrame tiene columnas como 'Country' y luego los años (ej: 'YR2022')
            for _, row in df.iterrows():
                country_name = row.get('Country', 'Unknown')
                country_id = row.name # I believe index is the ISO3 code
                
                # Iterar por las columnas de años
                for col in df.columns:
                    if col.startswith('YR'):
                        year = int(col.replace('YR', ''))
                        val = row[col]
                        
                        if pd.notna(val):
                            db.save_macro_metric(
                                indicator=ind_name,
                                country=country_name,
                                value=float(val),
                                year=year
                            )
                            
        print("[MACRO SERVICE] Sincronización completa.")
        return True
        
    except Exception as e:
        print(f"[MACRO SERVICE] Error: {e}")
        return False

if __name__ == "__main__":
    sync_worldbank_macro()
