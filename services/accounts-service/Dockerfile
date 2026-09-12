FROM python:3.12-slim
WORKDIR /srv

COPY services/accounts-service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY common ./common
COPY services/accounts-service/app ./app

# El comando por defecto sirve la API REST. El worker de eventos
# (coreografía) se lanza con el mismo image pero otro comando —
# ver docker-compose.yml, servicio accounts-service-worker.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
