from fastapi import APIRouter
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
    nda,
    payslip,
    payslip_component,
    feedback,
    shifts,
    milestone_roadmap,
    ai,
    google_auth,
    users,
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
api_router.include_router(nda.router)
api_router.include_router(payslip.router)
api_router.include_router(payslip_component.router)
api_router.include_router(feedback.router)
api_router.include_router(shifts.router)
api_router.include_router(milestone_roadmap.router)
api_router.include_router(ai.router)
api_router.include_router(google_auth.router, prefix="/auth/google", tags=["google-auth"])
api_router.include_router(users.router)
