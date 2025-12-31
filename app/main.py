from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.routes import (
    auth, roles, departments, employees, 
    expense_categories, expenses,
    document_categories, documents,
    clients, projects, holidays,
    asset_categories, assets, blogs, leave_types, leave_requests
)

app = FastAPI(title="Fair Tasker Backend")

app.mount("/static", StaticFiles(directory="static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(roles.router, prefix="/roles", tags=["roles"])
app.include_router(departments.router)
app.include_router(employees.router)
app.include_router(expense_categories.router)
app.include_router(expenses.router)
app.include_router(document_categories.router)
app.include_router(documents.router)
app.include_router(clients.router)
app.include_router(projects.router)
app.include_router(holidays.router)
app.include_router(asset_categories.router)
app.include_router(assets.router)
app.include_router(blogs.router)
app.include_router(leave_types.router)
app.include_router(leave_requests.router)

@app.get("/")
def read_root():
    return {"message": "Welcome to Fair Tasker Backend"}
