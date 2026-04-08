from pycoingecko import CoinGeckoAPI
import database as db

def sync_coingecko_global():
    """
    Obtiene métricas globales del mercado cripto desde CoinGecko.
    Ideal para monitorear la salud general del ecosistema (Cap de Mercado, Volumen 24h, Dominancia BTC).
    """
    try:
        cg = CoinGeckoAPI()
        
        # El endpoint /global de CoinGecko proporciona datos agregados del mercado
        global_data = cg.get_global()
        
        if 'data' in global_data:
            data = global_data['data']
            
            # total_market_cap y total_volume son diccionarios con moneda base (usd, eur, etc.)
            mcap = data.get('total_market_cap', {}).get('usd', 0)
            vol = data.get('total_volume', {}).get('usd', 0)
            
            # market_cap_percentage tiene los valores de dominancia
            btc_dom = data.get('market_cap_percentage', {}).get('btc', 0)
            
            db.save_crypto_global(
                market_cap=float(mcap),
                volume_24h=float(vol),
                btc_dominance=float(btc_dom)
            )
            
            print(f"[CRYPTO SERVICE] Global Sync: MCAP=${mcap:,.0f}, DOM={btc_dom:.1f}%")
            return True
        else:
            print("[CRYPTO SERVICE] Fail: No data in global request.")
            return False
            
    except Exception as e:
        print(f"[CRYPTO SERVICE] Error: {e}")
        return False

def sync_top_assets_price():
    """Sync prices for top cryptos from CoinGecko."""
    # Podríamos extenderlo luego
    pass

if __name__ == "__main__":
    sync_coingecko_global()
