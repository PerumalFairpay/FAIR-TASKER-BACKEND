from fastapi import FastAPI, Request, HTTPException, APIRouter
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from app.helper.response_helper import error_response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.routes import (
    auth,
    roles,
    departments,
    employees,
    expense_categories,
    expenses,
    document_categories,
    documents,
    clients,
    projects,
    holidays,
    asset_categories,
    assets,
    blogs,
    leave_types,
    leave_requests,
    tasks,
    attendance,
    permissions,
    dashboard,
    files,
    profile,
    checklist_templates,
    settings,
)

from app.jobs.scheduler import init_scheduler, shutdown_scheduler
import logging

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Fair Tasker Backend",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)


# Application startup event
@app.on_event("startup")
async def startup_event():
    """Initialize background jobs on application startup"""
    try:
        logger.info("Application starting up...")
        init_scheduler()
        logger.info("Background scheduler initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize scheduler: {str(e)}")


# Application shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Gracefully shutdown background jobs"""
    try:
        logger.info("Application shutting down...")
        shutdown_scheduler()
        logger.info("Background scheduler stopped successfully")
    except Exception as e:
        logger.error(f"Error during scheduler shutdown: {str(e)}")


app.mount("/static", StaticFiles(directory="static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "https://hrm.fairpaytechworks.com",
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
api_router.include_router(checklist_templates.router)
api_router.include_router(settings.router)


app.include_router(api_router, prefix="/api")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    formatted_errors = {}
    for error in exc.errors():
        loc = error.get("loc", [])
        # Skip the location type (body, query, etc.) if possible for cleaner field names
        if loc and loc[0] in ("body", "query", "path") and len(loc) > 1:
            field = ".".join(str(x) for x in loc[1:])
        else:
            field = ".".join(str(x) for x in loc)

        msg = error.get("msg")
        formatted_errors[field] = msg

    first_error_msg = "Validation failed"
    if exc.errors():
        error = exc.errors()[0]
        field = str(error.get("loc", ["field"])[-1])
        msg = error.get("msg", "invalid input")
        first_error_msg = f"{field.replace('_', ' ').capitalize()}: {msg}"

    return error_response(
        message=first_error_msg, errors=formatted_errors, status_code=422
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
