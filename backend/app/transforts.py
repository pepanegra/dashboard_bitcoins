import psycopg2
import os
import pandas as pd
from dotenv import load_dotenv
load_dotenv()

conn = None

try:
    
    conn = psycopg2.connect(
        host=os.getenv("host"),
        database=os.getenv("database"),
        user=os.getenv("user"),
        password=os.getenv("password"),
        port=os.getenv("port"),
        sslmode=os.getenv("sslmodete")
    ) 

except(psycopg2.DatabaseError(), Exception) as error:
    print(error)
    
finally:
    pass



df = pd.read_sql("""SELECT DISTINCT ON (c.id)
                    c.name,
                    p.current_price,
                    p.last_updated
                 FROM coins c 
                 JOIN prices p ON c.id = P.coin_id
                 ORDER BY c.id, p.last_updated DESC
                 """, conn)
                 
                 
print(pd)