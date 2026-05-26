import psycopg2
import pandas as pd
from psycopg2.extras import execute_values
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

# =============================================
# CONEXIONES
# =============================================
# SQLAlchemy — solo para leer con pd.read_sql
# psycopg2  — para escribir con ON CONFLICT

engine = create_engine(
    f"postgresql://{os.getenv('user')}:{os.getenv('password')}"
    f"@{os.getenv('host')}:{os.getenv('port')}/{os.getenv('database')}"
    f"?sslmode={os.getenv('sslmode')}"
)

conn = psycopg2.connect(
    host=os.getenv("host"),
    database=os.getenv("database"),
    user=os.getenv("user"),
    password=os.getenv("password"),
    port=os.getenv("port"),
    sslmode=os.getenv("sslmode")
)


# =============================================
# CREAR TABLAS Y RESTRICCIONES (primera vez)
# =============================================

with engine.connect() as c:
    # Crear tablas
    c.execute(text("""
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
    c.commit()

    # Restricciones UNIQUE — verificando si ya existen antes de crearlas
    constraints = [
        ("uq_comparar_symbol", "analysis_comparar_monedas", "symbol"),
        ("uq_ath_symbol",      "analysis_ath_atl",           "symbol"),
        ("uq_mercado_symbol",  "analysis_volumen_marketcap", "symbol"),
        ("uq_supply_symbol",   "analysis_supply",            "symbol"),
    ]

    for constraint_name, tabla, columna in constraints:
        # Verifica si la restricción ya existe en PostgreSQL
        resultado = c.execute(text("""
            SELECT COUNT(*) FROM information_schema.table_constraints
            WHERE constraint_name = :nombre
        """), {"nombre": constraint_name})

        # Si no existe (COUNT = 0) la crea
        if resultado.fetchone()[0] == 0:  # pyright: ignore[reportOptionalSubscript]
            c.execute(text(f"""
                ALTER TABLE {tabla}
                ADD CONSTRAINT {constraint_name} UNIQUE ({columna})
            """))
            print(f"  ✓ Restricción {constraint_name} creada")
        else:
            print(f"  · {constraint_name} ya existe")

    c.commit()
    print("✓ Tablas y restricciones listas")


# =============================================
# FUNCIÓN AUXILIAR — guardar con ON CONFLICT
# =============================================
# execute_values inserta todas las filas de una vez
# en lugar de fila por fila — mucho más rápido.
# conflict_column — columna que detecta duplicados
# update_columns  — columnas que se actualizan si ya existe

def save_df(conn, df, tabla, conflict_column, update_columns):
    cursor = conn.cursor()

    # Convierte cada fila del DataFrame a una tupla
    rows = [tuple(row) for row in df.itertuples(index=False)]

    # Construye dinámicamente el SET del ON CONFLICT
    # Ejemplo: "current_price = EXCLUDED.current_price, ..."
    update_set = ", ".join([f"{col} = EXCLUDED.{col}" for col in update_columns])

    # Nombres de columnas separados por coma
    columns = ", ".join(df.columns)

    sql = f"""
        INSERT INTO {tabla} ({columns})
        VALUES %s
        ON CONFLICT ({conflict_column}) DO UPDATE
        SET {update_set}
    """

    execute_values(cursor, sql, rows)
    conn.commit()
    cursor.close()


# =============================================
# 1. COMPARAR MONEDAS ENTRE SÍ
# =============================================
# DISTINCT ON (c.id) trae solo el precio más reciente
# por moneda — sin duplicados.

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

save_df(
    conn             = conn,
    df               = df_comparar,
    tabla            = "analysis_comparar_monedas",
    conflict_column  = "symbol",
    update_columns   = ["current_price", "high_24h", "low_24h",
                        "price_change_pct_24h", "last_updated"]
)
print("✓ analysis_comparar_monedas guardado —", len(df_comparar), "filas")


# =============================================
# 2. DISTANCIA AL ATH / ATL
# =============================================
# ath_change_pct viene negativo desde la API.
# abs() lo convierte a positivo para el frontend.

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

save_df(
    conn             = conn,
    df               = df_ath,
    tabla            = "analysis_ath_atl",
    conflict_column  = "symbol",
    update_columns   = ["ath", "ath_date", "ath_change_pct",
                        "atl", "atl_date", "atl_change_pct",
                        "distancia_ath_pct"]
)
print("✓ analysis_ath_atl guardado —", len(df_ath), "filas")


# =============================================
# 3. VOLUMEN VS MARKET CAP
# =============================================
# ratio_liquidez = (volumen / market_cap) * 100
# fillna(0) evita errores con valores nulos.
# replace(0, nan) evita división por cero.

df_mercado = pd.read_sql("""
    SELECT DISTINCT ON (c.id)
        c.name, c.symbol,
        m.market_cap, m.total_volume,
        m.market_cap_change_pct_24h, m.last_updated
    FROM coins c
    JOIN market_data m ON c.id = m.coin_id
    ORDER BY c.id, m.last_updated DESC
""", engine)

df_mercado["market_cap"]         = pd.to_numeric(df_mercado["market_cap"]).fillna(0)
df_mercado["total_volume"]       = pd.to_numeric(df_mercado["total_volume"]).fillna(0)
df_mercado["last_updated"]       = pd.to_datetime(df_mercado["last_updated"])
df_mercado["ratio_liquidez_pct"] = (
    df_mercado["total_volume"] /
    df_mercado["market_cap"].replace(0, float("nan")) * 100
).round(4)
df_mercado = df_mercado.sort_values("market_cap", ascending=False).reset_index(drop=True)

save_df(
    conn             = conn,
    df               = df_mercado,
    tabla            = "analysis_volumen_marketcap",
    conflict_column  = "symbol",
    update_columns   = ["market_cap", "total_volume",
                        "market_cap_change_pct_24h",
                        "ratio_liquidez_pct", "last_updated"]
)
print("✓ analysis_volumen_marketcap guardado —", len(df_mercado), "filas")


# =============================================
# 4. SUPPLY MINADO VS RESTANTE
# =============================================
# pct_minado = cuánto % del total ya fue emitido.
# restante   = cuántos tokens faltan por emitir.
# WHERE max_supply IS NOT NULL — solo monedas con límite.

df_supply = pd.read_sql("""
    SELECT c.name, c.symbol,
           s.circulating_supply, s.total_supply, s.max_supply
    FROM coins c
    JOIN supply s ON c.id = s.coin_id
    WHERE s.max_supply IS NOT NULL
    ORDER BY s.circulating_supply DESC
""", engine)

df_supply["circulating_supply"] = pd.to_numeric(df_supply["circulating_supply"])
df_supply["total_supply"]       = pd.to_numeric(df_supply["total_supply"])
df_supply["max_supply"]         = pd.to_numeric(df_supply["max_supply"])
df_supply["pct_minado"]         = (
    df_supply["circulating_supply"] / df_supply["max_supply"] * 100
).round(2)
df_supply["restante"] = df_supply["max_supply"] - df_supply["circulating_supply"]

save_df(
    conn             = conn,
    df               = df_supply,
    tabla            = "analysis_supply",
    conflict_column  = "symbol",
    update_columns   = ["circulating_supply", "total_supply",
                        "max_supply", "pct_minado", "restante"]
)
print("✓ analysis_supply guardado —", len(df_supply), "filas")


# =============================================
# VERIFICACIÓN FINAL
# =============================================

tablas = [
    "analysis_comparar_monedas",
    "analysis_ath_atl",
    "analysis_volumen_marketcap",
    "analysis_supply"
]

print("\n── Verificación ─────────────────────────────")
with engine.connect() as c:
    for tabla in tablas:
        resultado = c.execute(text(f"SELECT COUNT(*) FROM {tabla}"))
        count = resultado.fetchone()[0] # pyright: ignore[reportOptionalSubscript]
        print(f"  {tabla}: {count} filas")

print("\n✓ Transformaciones completadas")

# Cierra todas las conexiones
conn.close()
engine.dispose()
