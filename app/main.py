from fastapi import FastAPI
from app.routes import auth, roles, users, departments

app = FastAPI(title="Fair Tasker Backend")

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(roles.router, prefix="/roles", tags=["roles"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(departments.router, prefix="/departments", tags=["departments"])

@app.get("/")
def read_root():
    return {"message": "Welcome to Fair Tasker Backend"}
