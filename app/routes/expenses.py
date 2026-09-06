from fastapi import APIRouter, Depends, UploadFile, File, Form
from app.services.api.expense import ExpenseService
from app.helper.response_helper import success_response, error_response
from typing import Optional
from app.auth import verify_token, require_permission

router = APIRouter(prefix="/expenses", tags=["expenses"], dependencies=[Depends(verify_token)])


@router.post("/create", dependencies=[Depends(require_permission("expense:submit"))])
async def create_expense(
    expense_category_id: str = Form(...),
    amount: float = Form(...),
    purpose: str = Form(...),
    payment_mode: str = Form(...),
    date: str = Form(...),
    expense_subcategory_id: Optional[str] = Form(None),
    attachment: Optional[UploadFile] = File(None)
):
    data, error = await ExpenseService.create(
        expense_category_id=expense_category_id,
        expense_subcategory_id=expense_subcategory_id,
        amount=amount,
        purpose=purpose,
        payment_mode=payment_mode,
        date=date,
        attachment=attachment
    )
    if error:
        return error_response(message=f"Failed to create expense: {error}", status_code=500)
    return success_response(message="Expense created successfully", data=data, status_code=201)


@router.get("/all", dependencies=[Depends(require_permission("expense:view"))])
async def get_expenses():
    data, error = await ExpenseService.list()
    if error:
        return error_response(message=f"Failed to fetch expenses: {error}", status_code=500)
    return success_response(message="Expenses fetched successfully", data=data)


@router.get("/{expense_id}", dependencies=[Depends(require_permission("expense:view"))])
async def get_expense(expense_id: str):
    data, error = await ExpenseService.get(expense_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Expense fetched successfully", data=data)


@router.put("/update/{expense_id}", dependencies=[Depends(require_permission("expense:submit"))])
async def update_expense(
    expense_id: str,
    expense_category_id: Optional[str] = Form(None),
    expense_subcategory_id: Optional[str] = Form(None),
    amount: Optional[float] = Form(None),
    purpose: Optional[str] = Form(None),
    payment_mode: Optional[str] = Form(None),
    date: Optional[str] = Form(None),
    attachment: Optional[UploadFile] = File(None)
):
    data, error = await ExpenseService.update(
        expense_id=expense_id,
        expense_category_id=expense_category_id,
        expense_subcategory_id=expense_subcategory_id,
        amount=amount,
        purpose=purpose,
        payment_mode=payment_mode,
        date=date,
        attachment=attachment
    )
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Expense updated successfully", data=data)


@router.delete("/delete/{expense_id}", dependencies=[Depends(require_permission("expense:submit"))])
async def delete_expense(expense_id: str):
    success, error = await ExpenseService.delete(expense_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Expense deleted successfully", data=[])
