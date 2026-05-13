import pandas as pd
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

# =============================================
# CONEXIÓN CON SQLALCHEMY
# =============================================
# SQLAlchemy es el conector que pandas requiere para
# read_sql y to_sql — permite leer y escribir DataFrames
# directamente desde/hacia PostgreSQL sin conversiones manuales.

engine = create_engine(
    f"postgresql://{os.getenv('user')}:{os.getenv('password')}"
    f"@{os.getenv('host')}:{os.getenv('port')}/{os.getenv('database')}"
    f"?sslmode={os.getenv('sslmode')}"
)


# =============================================
# CREAR TABLAS DE ANÁLISIS (solo primera vez)
# =============================================
# IF NOT EXISTS evita error si ya existen.

with engine.connect() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS analysis_precio_historico (
            name                 VARCHAR,
            symbol               VARCHAR,
            current_price        NUMERIC,
            price_change_pct_24h NUMERIC,
            last_updated         TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS analysis_comparar_monedas (
            name                 VARCHAR,
            symbol               VARCHAR,
            market_cap_rank      INT,
            current_price        NUMERIC,
            high_24h             NUMERIC,
            low_24h              NUMERIC,
            price_change_pct_24h NUMERIC,
            last_updated         TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS analysis_ath_atl (
            name              VARCHAR,
            symbol            VARCHAR,
            ath               NUMERIC,
            ath_date          TIMESTAMP,
            ath_change_pct    NUMERIC,
            atl               NUMERIC,
            atl_date          TIMESTAMP,
            atl_change_pct    NUMERIC,
            distancia_ath_pct NUMERIC
        );

        CREATE TABLE IF NOT EXISTS analysis_volumen_marketcap (
            name                      VARCHAR,
            symbol                    VARCHAR,
            market_cap                NUMERIC,
            total_volume              NUMERIC,
            market_cap_change_pct_24h NUMERIC,
            ratio_liquidez_pct        NUMERIC,
            last_updated              TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS analysis_supply (
            name               VARCHAR,
            symbol             VARCHAR,
            circulating_supply NUMERIC,
            total_supply       NUMERIC,
            max_supply         NUMERIC,
            pct_minado         NUMERIC,
            restante           NUMERIC
        );
    """))
    conn.commit()
    print("✓ Tablas de análisis creadas")


# =============================================
# 1. EVOLUCIÓN DEL PRECIO EN EL TIEMPO
# =============================================
# pd.read_sql ejecuta el query y retorna un DataFrame
# directamente — no necesitas fetchall() ni cursor.
# pd.to_datetime convierte las fechas a objetos datetime
# reales para poder filtrar y graficar por tiempo.

df_precios = pd.read_sql("""
    SELECT c.name, c.symbol, p.current_price,
           p.price_change_pct_24h, p.last_updated
    FROM coins c
    JOIN prices p ON c.id = p.coin_id
    ORDER BY c.id, p.last_updated ASC
""", engine)

df_precios["last_updated"]         = pd.to_datetime(df_precios["last_updated"])
df_precios["current_price"]        = pd.to_numeric(df_precios["current_price"])
df_precios["price_change_pct_24h"] = pd.to_numeric(df_precios["price_change_pct_24h"])

# to_sql guarda el DataFrame en la tabla indicada.
# if_exists="replace" borra y reescribe la tabla cada vez.
# if_exists="append"  agrega filas sin borrar las anteriores.
# index=False evita guardar el índice numérico de pandas como columna.
df_precios.to_sql("analysis_precio_historico", engine, if_exists="replace", index=False)
print("✓ analysis_precio_historico guardado —", len(df_precios), "filas")


# =============================================
# 2. COMPARAR MONEDAS ENTRE SÍ
# =============================================
# DISTINCT ON (c.id) trae solo el registro más reciente
# por moneda — evita duplicados en el análisis.
# sort_values ordena por precio descendente.
# reset_index(drop=True) reinicia el índice 0,1,2...
# después de ordenar.

df_comparar = pd.read_sql("""
    SELECT DISTINCT ON (c.id)
        c.name, c.symbol, c.market_cap_rank,
        p.current_price, p.high_24h, p.low_24h,
        p.price_change_pct_24h, p.last_updated
    FROM coins c
    JOIN prices p ON c.id = p.coin_id
    ORDER BY c.id, p.last_updated DESC
""", engine)

df_comparar["current_price"]        = pd.to_numeric(df_comparar["current_price"])
df_comparar["price_change_pct_24h"] = pd.to_numeric(df_comparar["price_change_pct_24h"])
df_comparar["last_updated"]         = pd.to_datetime(df_comparar["last_updated"])
df_comparar = df_comparar.sort_values("current_price", ascending=False).reset_index(drop=True)

df_comparar.to_sql("analysis_comparar_monedas", engine, if_exists="replace", index=False)
print("✓ analysis_comparar_monedas guardado —", len(df_comparar), "filas")


# =============================================
# 3. DISTANCIA AL ATH / ATL
# =============================================
# ath_change_pct viene negativo desde la API
# (ej: -40.67 = está 40.67% por debajo del ATH).
# abs() convierte a positivo — más fácil de leer
# y graficar desde el frontend.

df_ath = pd.read_sql("""
    SELECT c.name, c.symbol,
           h.ath, h.ath_date, h.ath_change_pct,
           h.atl, h.atl_date, h.atl_change_pct
    FROM coins c
    JOIN history h ON c.id = h.coin_id
    ORDER BY h.ath_change_pct DESC
""", engine)

df_ath["ath_change_pct"]    = pd.to_numeric(df_ath["ath_change_pct"])
df_ath["atl_change_pct"]    = pd.to_numeric(df_ath["atl_change_pct"])
df_ath["ath_date"]          = pd.to_datetime(df_ath["ath_date"])
df_ath["atl_date"]          = pd.to_datetime(df_ath["atl_date"])
df_ath["distancia_ath_pct"] = df_ath["ath_change_pct"].abs()

df_ath.to_sql("analysis_ath_atl", engine, if_exists="replace", index=False)
print("✓ analysis_ath_atl guardado —", len(df_ath), "filas")


# =============================================
# 4. VOLUMEN VS MARKET CAP
# =============================================
# fillna(0) reemplaza None/NaN con 0 para no romper
# la división al calcular el ratio de liquidez.
# replace(0, nan) en el divisor evita división por cero.
# round(4) redondea a 4 decimales para legibilidad.

df_mercado = pd.read_sql("""
    SELECT DISTINCT ON (c.id)
        c.name, c.symbol,
        m.market_cap, m.total_volume,
        m.market_cap_change_pct_24h, m.last_updated
    FROM coins c
    JOIN market_data m ON c.id = m.coin_id
    ORDER BY c.id, m.last_updated DESC
""", engine)

df_mercado["market_cap"]   = pd.to_numeric(df_mercado["market_cap"]).fillna(0)
df_mercado["total_volume"] = pd.to_numeric(df_mercado["total_volume"]).fillna(0)
df_mercado["last_updated"] = pd.to_datetime(df_mercado["last_updated"])

df_mercado["ratio_liquidez_pct"] = (
    df_mercado["total_volume"] /
    df_mercado["market_cap"].replace(0, float("nan")) * 100
).round(4)

df_mercado = df_mercado.sort_values("market_cap", ascending=False).reset_index(drop=True)

df_mercado.to_sql("analysis_volumen_marketcap", engine, if_exists="replace", index=False)
print("✓ analysis_volumen_marketcap guardado —", len(df_mercado), "filas")


# =============================================
# 5. SUPPLY MINADO VS RESTANTE
# =============================================
# Solo monedas con max_supply definido (WHERE en SQL)
# para evitar división por None en pandas.
# pct_minado = cuánto % del total ya fue emitido.
# restante   = cuántos tokens faltan por emitir.

df_supply = pd.read_sql("""
    SELECT c.name, c.symbol,
           s.circulating_supply, s.total_supply, s.max_supply
    FROM coins c
    JOIN supply s ON c.id = s.coin_id
    WHERE s.max_supply IS NOT NULL
    ORDER BY s.circulating_supply DESC
""", engine)

df_supply["circulating_supply"] = pd.to_numeric(df_supply["circulating_supply"])
df_supply["max_supply"]         = pd.to_numeric(df_supply["max_supply"])
df_supply["total_supply"]       = pd.to_numeric(df_supply["total_supply"])

df_supply["pct_minado"] = (
    df_supply["circulating_supply"] / df_supply["max_supply"] * 100
).round(2)

df_supply["restante"] = df_supply["max_supply"] - df_supply["circulating_supply"]

df_supply.to_sql("analysis_supply", engine, if_exists="replace", index=False)
print("✓ analysis_supply guardado —", len(df_supply), "filas")


# =============================================
# VERIFICACIÓN FINAL
# =============================================
# Leemos cuántas filas quedaron en cada tabla
# para confirmar que todo se guardó correctamente.

tablas = [
    "analysis_precio_historico",
    "analysis_comparar_monedas",
    "analysis_ath_atl",
    "analysis_volumen_marketcap",
    "analysis_supply"
]

print("\n── Verificación ─────────────────────────────")
with engine.connect() as conn:
    for tabla in tablas:
        resultado = conn.execute(text(f"SELECT COUNT(*) FROM {tabla}"))
        count = resultado.fetchone()[0]
        print(f"  {tabla}: {count} filas")

print("\n✓ Transformaciones completadas")
engine.dispose()  # Cierra todas las conexiones del pool
