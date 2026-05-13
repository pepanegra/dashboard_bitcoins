import requests
import os




def get_data():
    
    r = requests.get(os.getenv("api"))

    if r.status_code  == 200:
        print("Peticion exiotosa")
        return r.json()
    
    elif r.status_code == 400:
        print("No encontrado")
        return None
        
    else:
        print(f'Error: {r.status_code}')
        return None
    





print(os.getenv("host"))
print(os.getenv("user"))