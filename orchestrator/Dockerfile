FROM python:3.12-slim
WORKDIR /srv

COPY orchestrator/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY common ./common
COPY orchestrator/flows ./flows
COPY orchestrator/api.py ./api.py
COPY orchestrator/run_demo.py ./run_demo.py

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "4200"]
