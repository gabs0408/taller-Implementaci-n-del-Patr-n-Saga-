FROM python:3.12-slim
WORKDIR /srv
ENV PYTHONUNBUFFERED=1

COPY services/risk-service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY common ./common
COPY services/risk-service/app ./app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
