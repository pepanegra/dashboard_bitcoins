#Importando dependencias y modulos
from apscheduler.schedulers.blocking import BlockingScheduler
from app.bd import run_pipelines 


scheduler = BlockingScheduler()

scheduler.add_job(run_pipelines,'interval', hours=2)
if __name__ == "__main__":
    scheduler.start()