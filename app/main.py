from fastapi import FastAPI
from app.routes import auth, roles

app = FastAPI(title="Fair Tasker Backend")

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(roles.router, prefix="/roles", tags=["roles"])

@app.get("/")
def read_root():
    return {"message": "Welcome to Fair Tasker Backend"}
