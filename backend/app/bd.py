#Importando los modulos y la data 
import psycopg2
from .peticions import get_data
import os
from dotenv import load_dotenv
load_dotenv()



# Define esto arriba del for, antes del loop
def to_float(value):
        """Convierte a float, retorna None si el valor es None."""
        return float(value) if value is not None else None
    
    
    
#Funciones para guardar cada tabla en bases de datos
def save_coins (cursor,dt):
    if dt:
        # Itera sobre cada moneda obtenida desde la API
        for item in dt:
            
                # ── COINS ──────────────────────────────────────────
                # Extrae los datos de identificación de la moneda
                coin_id         = item["id"]
                symbol          = item["symbol"]
                name            = item["name"]
                image_url       = item["image"]
                market_cap_rank = item["market_cap_rank"]
        
                # Inserta la moneda, si ya existe actualiza sus datos
                cursor.execute("""
                    INSERT INTO coins (id, symbol, name, image_url, market_cap_rank)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE
                    SET
                        symbol          = EXCLUDED.symbol,
                        name            = EXCLUDED.name,
                        image_url       = EXCLUDED.image_url,
                        market_cap_rank = EXCLUDED.market_cap_rank
                """, (coin_id, symbol, name, image_url, market_cap_rank))
 
def save_prices (cursor, dt): 
    if dt:  
        for item in dt:   
         # ── PRICES ─────────────────────────────────────────
         # Extrae los datos de precio del momento actual
         coin_id         = item["id"]
         current_price        = item["current_price"]
         high_24h             = item["high_24h"]
         low_24h              = item["low_24h"]
         price_change_24h     = item["price_change_24h"]
         price_change_pct_24h      = to_float(item["price_change_percentage_24h"])
         last_updated         = item["last_updated"]
         # Siempre inserta un nuevo registro para conservar el historial de precios
         # No usa ON CONFLICT porque queremos guardar cada snapshot en el tiempo
         
         cursor.execute("""
            INSERT INTO prices (coin_id, current_price, high_24h, low_24h,
                                 price_change_24h, price_change_pct_24h, last_updated)
             VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (coin_id, current_price, high_24h, low_24h,
               price_change_24h, price_change_pct_24h, last_updated))
    else:
        print("No hay informacion disponible")

def save_market_data (cursor, dt):
    if dt:
        for item in dt:        
            # ── MARKET DATA ────────────────────────────────────
            # Extrae los datos de capitalización y volumen de mercado
            coin_id         = item["id"]
            market_cap                = item["market_cap"]
            fully_diluted_valuation   = item["fully_diluted_valuation"]
            total_volume              = item["total_volume"]
            market_cap_change_24h     = item["market_cap_change_24h"]
            market_cap_change_pct_24h     = to_float(item["market_cap_change_percentage_24h"])
            last_updated         = item["last_updated"]
    
            # Inserta o actualiza los datos de mercado de la moneda
            cursor.execute("""
                INSERT INTO market_data (coin_id, market_cap, fully_diluted_valuation, total_volume,
                                         market_cap_change_24h, market_cap_change_pct_24h, last_updated)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (coin_id) DO UPDATE
                SET
                    market_cap                = EXCLUDED.market_cap,
                    fully_diluted_valuation   = EXCLUDED.fully_diluted_valuation,
                    total_volume              = EXCLUDED.total_volume,
                    market_cap_change_24h     = EXCLUDED.market_cap_change_24h,
                    market_cap_change_pct_24h = EXCLUDED.market_cap_change_pct_24h,
                    last_updated              = EXCLUDED.last_updated
               
            """, (coin_id, market_cap, fully_diluted_valuation, total_volume,
                  market_cap_change_24h, market_cap_change_pct_24h , last_updated))
    else:print("No hay informacion disponible en estos momentos")


def save_supply (cursor, dt):
    if dt:
        for item in dt:
            # ── SUPPLY ─────────────────────────────────────────
            # Extrae los datos de oferta de la moneda
            # max_supply puede ser None si la moneda no tiene límite de emisión (ej. Ethereum)
            coin_id         = item["id"]
            circulating_supply = item["circulating_supply"]
            total_supply       = item["total_supply"]
            max_supply         = item["max_supply"]
    
            # Inserta o actualiza la oferta — cambia poco pero se mantiene al día
            cursor.execute("""
                INSERT INTO supply (coin_id, circulating_supply, total_supply, max_supply)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (coin_id) DO UPDATE
                SET
                    circulating_supply = EXCLUDED.circulating_supply,
                    total_supply       = EXCLUDED.total_supply,
                    max_supply         = EXCLUDED.max_supply
            """, (coin_id, circulating_supply, total_supply, max_supply))
    else:print("No hay informacion disponible")
    
def save_history (cursor, dt):
    if dt:
        for item in dt:
        # ── HISTORY ────────────────────────────────────────
        # Extrae los máximos y mínimos históricos de la moneda
            coin_id         = item["id"]
            ath            = item["ath"]           # all-time high: precio más alto histórico
            ath_date       = item["ath_date"]      # fecha en que se alcanzó el ATH
            ath_change_pct            = to_float(item["ath_change_percentage"]) # % de distancia al ATH (negativo = bajo el ATH)
            atl            = item["atl"]           # all-time low: precio más bajo histórico
            atl_date       = item["atl_date"]      # fecha en que se alcanzó el ATL
            atl_change_pct            = to_float(item["atl_change_percentage"])  # % de distancia al ATL (positivo = subió desde ATL)
    
            # Inserta o actualiza el historial — el ATH/ATL puede cambiar si se rompe un récord
            cursor.execute("""
                INSERT INTO history (coin_id, ath, ath_date, ath_change_pct, atl, atl_date, atl_change_pct)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (coin_id) DO UPDATE
                SET
                    ath            = EXCLUDED.ath,
                    ath_date       = EXCLUDED.ath_date,
                    ath_change_pct = EXCLUDED.ath_change_pct,
                    atl            = EXCLUDED.atl,
                    atl_date       = EXCLUDED.atl_date,
                    atl_change_pct = EXCLUDED.atl_change_pct
            """, (coin_id, ath, ath_date, ath_change_pct, atl, atl_date, atl_change_pct))

                
def run_pipelines ():
    dt = get_data()
    conn = None
    try:
        # Abre la conexión a la base de datos usando la configuración definida en DB_CONFIG
        conn = psycopg2.connect(
            host=os.getenv("host"),
            database=os.getenv("database"),
            user=os.getenv("user"),
            password=os.getenv("password"),
            port=os.getenv("port"),
            sslmode=os.getenv("sslmodete")
        )
        if conn:
            print("Abriendo conexion segura")
        else:
            print("no se puede realizar la conexion")
        #Abriendo el cursor
        cursor = conn.cursor()
        #Ejecutando las funciiones para guardar la informacion en las tablas
        save_coins(cursor,dt)
        save_prices(cursor,dt)
        save_market_data(cursor,dt)
        save_supply(cursor,dt)
        save_history(cursor,dt)
        
            
    except (psycopg2.DatabaseError, Exception) as error: 
            print(error)
    finally:
            if conn is not None:
                conn.commit()
                cursor.close()
                conn.close()
                print('Operacion exitosa!!!')
                print(conn)
            else:print("No hay conexion")
        
    
run_pipelines()


