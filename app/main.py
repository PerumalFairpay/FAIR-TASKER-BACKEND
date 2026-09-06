from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import logging

from app.helper.response_helper import error_response
from app.routes.router import api_router
from app.jobs.scheduler import init_scheduler, shutdown_scheduler
from app.cookies.cookies import get_manager

logger = logging.getLogger(__name__)

app = FastAPI(
    title="HRM Backend",
    version="1.0.0",
    docs_url="/",
    redoc_url="/api/redoc",
    root_path="/api"
)


# Application startup event
@app.on_event("startup")
async def startup_event():
    """Initialize background jobs on application startup"""
    try:
        manager = get_manager()
        await manager.init_redis()
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
        manager = get_manager()
        await manager.close_redis()
        logger.info("Application shutting down...")
        shutdown_scheduler()
        logger.info("Background scheduler stopped successfully")
    except Exception as e:
        logger.error(f"Error during scheduler shutdown: {str(e)}")


app.mount("/static", StaticFiles(directory="static"), name="static")

origins = [
    "https://hrm.fairpaytechworks.com",
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:3002",
    "http://192.168.1.42:3000",
    "http://192.168.1.42:3001"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    formatted_errors = {}
    for error in exc.errors():
        loc = error.get("loc", [])
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
    return {"message": "Welcome to FairPay Backend"}
