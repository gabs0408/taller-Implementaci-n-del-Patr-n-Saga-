from fastapi import FastAPI

from .routes import router

app = FastAPI(title="NovaBank Saga — Clearing Service")
app.include_router(router)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
