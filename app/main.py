from fastapi import FastAPI
from app.routes import auth

app = FastAPI(title="Fair Tasker Backend")

app.include_router(auth.router, prefix="/auth", tags=["auth"])

@app.get("/")
def read_root():
    return {"message": "Welcome to Fair Tasker Backend"}
