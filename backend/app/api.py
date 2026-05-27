#Importando librerias
from fastapi import FastAPI
import psycopg2
from psycopg2 import sql
import os
import asyncio
import math
from dotenv import load_dotenv
load_dotenv()

#crenando la instancia de FastAPI
app = FastAPI()

def infodb (name_table):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(
            host=os.getenv("host"),
            database=os.getenv("database"),
            user=os.getenv("user"),
            password=os.getenv("password"),
            port=os.getenv("port"),
            sslmode=os.getenv("sslmodete")
        )
        cursor = conn.cursor()
        query = sql.SQL("SELECT * FROM {}").format(sql.Identifier(name_table))
        cursor.execute(query)
        info = cursor.fetchall()
        def limpiar_nan(info):
            return [
                tuple(None if isinstance(x, float) and math.isnan(x) else x for x in tupla)
                for tupla in info
            ]
        info_limpia = limpiar_nan(info)
        return info_limpia
        
    except(psycopg2.DatabaseError,Exception) as error:
        print("Mensagge : Erro al intentar obtener la informacion")
    finally:
        if conn is not None:
            if cursor is not None:
                cursor.close() # type: ignore
            conn.commit()
            conn.close()
            print('Operacion exitosa!!!')
           
        else:
            print("No hay conexion")

@app.get("/")
async def root():
    return {"message": "Hello World"}


#obtener la informacion de la tabla analysis_comparar_monedas
@app.get("/analysis_comparar_monedas")
async def comparar_monedas():
    info = infodb("analysis_comparar_monedas")
    return {"data": info}


#obtener la informacion de la tabla analysis_ath_atl
@app.get("/analysis_ath_atl")
async def ath_atl():
    info = infodb("analysis_ath_atl")
    return {"data": info}


#obtener la informacion de la tabla analysis_volumen_marketcap
@app.get("/analysis_volumen_marketcap")
async def volumen_marketcap():
    info = infodb("analysis_volumen_marketcap")
    return {"data": info}

#obtener la informacion de la tabla analysis_supply
@app.get("/analysis_supply")
async def supply():
    info = infodb("analysis_supply")
    return {"data": info}


