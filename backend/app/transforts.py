#Importan las librerias necesarias
import os
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
load_dotenv()




#Creando las variables para conectar el engine  
DATABASE_URL = (
f"postgresql+psycopg2://{os.getenv('user')}:"
f"{os.getenv('password')}@"
f"{os.getenv('host')}:"
f"{os.getenv('port')}/"
f"{os.getenv('database')}"
)

#supervisando que las variables de entorno si se lean
if "None" in DATABASE_URL: raise ValueError("Error: variables de entorno no cargadas")


#creando el motor engine
engine = create_engine(
    #Pasando la tupla con las variables de entorno
    DATABASE_URL,
    #conectando con sslmode
    connect_args={
        "sslmode": os.getenv("sslmode"),
        "options": "-c client_encoding=utf8"
    }
)

#formando la query
query = """SELECT DISTINCT ON (c.id)
                    c.name,
                    p.current_price,
                    p.last_updated
                 FROM coins c 
                 JOIN prices p ON c.id = p.coin_id
                 ORDER BY c.id, p.last_updated DESC
                 """

df = pd.read_sql(query, engine)

     
print(df)



#Corregir error de codificacion en la base de datos