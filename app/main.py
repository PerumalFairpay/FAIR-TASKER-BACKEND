from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import (
    auth, roles, departments, employees, 
    expense_categories, expenses,
    document_categories, documents
)

app = FastAPI(title="Fair Tasker Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(roles.router, prefix="/roles", tags=["roles"])
app.include_router(departments.router)
app.include_router(employees.router)
app.include_router(expense_categories.router)
app.include_router(expenses.router)
app.include_router(document_categories.router)
app.include_router(documents.router)

@app.get("/")
def read_root():
    return {"message": "Welcome to Fair Tasker Backend"}
