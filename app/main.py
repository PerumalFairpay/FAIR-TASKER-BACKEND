from fastapi import FastAPI, Request, HTTPException, APIRouter
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from app.helper.response_helper import error_response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.routes import (
    auth, roles, departments, employees, 
    expense_categories, expenses,
    document_categories, documents,
    clients, projects, holidays,
    asset_categories, assets, blogs, leave_types, leave_requests, tasks, attendance, permissions, dashboard, files, profile
)

app = FastAPI(title="Fair Tasker Backend", version="1.0.0", docs_url="/api/docs", redoc_url="/api/redoc")

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

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(roles.router, prefix="/roles", tags=["roles"])
api_router.include_router(departments.router)
api_router.include_router(employees.router)
api_router.include_router(expense_categories.router)
api_router.include_router(expenses.router)
api_router.include_router(document_categories.router)
api_router.include_router(documents.router)
api_router.include_router(clients.router)
api_router.include_router(projects.router)
api_router.include_router(holidays.router)
api_router.include_router(asset_categories.router)
api_router.include_router(assets.router)
api_router.include_router(blogs.router)
api_router.include_router(leave_types.router)
api_router.include_router(leave_requests.router)
api_router.include_router(tasks.router)
api_router.include_router(attendance.router)
api_router.include_router(permissions.router)
api_router.include_router(dashboard.router)
api_router.include_router(files.router)
api_router.include_router(profile.router)

app.include_router(api_router, prefix="/api")
 
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return error_response(
        message="Validation failed",
        errors=exc.errors(),
        status_code=422
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return error_response(message=exc.detail, status_code=exc.status_code)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return error_response(message=str(exc), status_code=500)


@app.get("/")
def read_root():
    return {"message": "Welcome to Fair Tasker Backend"}
