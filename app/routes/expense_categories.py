from fastapi import APIRouter, Depends
from app.models import ExpenseCategoryCreate, ExpenseCategoryUpdate
from app.services.api.expense_category import ExpenseCategoryService
from app.helper.response_helper import success_response, error_response
from app.auth import verify_token, require_permission

router = APIRouter(prefix="/expense-categories", tags=["expense-categories"], dependencies=[Depends(verify_token)])


@router.post("/create", dependencies=[Depends(require_permission("expense:submit"))])
async def create_category(category: ExpenseCategoryCreate):
    data, error = await ExpenseCategoryService.create(category)
    if error:
        return error_response(message=f"Failed to create category: {error}", status_code=500)
    return success_response(message="Category created successfully", data=data, status_code=201)


@router.get("/all", dependencies=[Depends(require_permission("expense:view"))])
async def get_categories():
    data, error = await ExpenseCategoryService.list()
    if error:
        return error_response(message=f"Failed to fetch categories: {error}", status_code=500)
    return success_response(message="Categories fetched successfully", data=data)


@router.get("/{category_id}", dependencies=[Depends(require_permission("expense:view"))])
async def get_category(category_id: str):
    data, error = await ExpenseCategoryService.get(category_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Category fetched successfully", data=data)


@router.put("/update/{category_id}", dependencies=[Depends(require_permission("expense:submit"))])
async def update_category(category_id: str, category: ExpenseCategoryUpdate):
    data, error = await ExpenseCategoryService.update(category_id, category)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Category updated successfully", data=data)


@router.delete("/delete/{category_id}", dependencies=[Depends(require_permission("expense:submit"))])
async def delete_category(category_id: str):
    success, error = await ExpenseCategoryService.delete(category_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Category deleted successfully", data=[])
