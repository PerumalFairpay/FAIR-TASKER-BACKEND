from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import JSONResponse
from app.crud.repository import repository as repo
from app.models import ExpenseCreate, ExpenseUpdate
from app.helper.file_handler import save_file, delete_file
from typing import List, Optional
import json

router = APIRouter(prefix="/expenses", tags=["expenses"])

@router.post("/create")
async def create_expense(
    expense_category_id: str = Form(...),
    amount: float = Form(...),
    purpose: str = Form(...),
    payment_mode: str = Form(...),
    date: str = Form(...),
    attachment: UploadFile = File(None)
):
    try:
        attachment_path = None
        if attachment:
            attachment_path = await save_file(attachment, "attachments")

        expense_data = ExpenseCreate(
            expense_category_id=expense_category_id,
            amount=amount,
            purpose=purpose,
            payment_mode=payment_mode,
            date=date
        )

        new_expense = await repo.create_expense(expense_data, attachment_path)
        return JSONResponse(
            status_code=201,
            content={"message": "Expense created successfully", "success": True, "data": new_expense}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to create expense: {str(e)}", "success": False}
        )

@router.get("/all")
async def get_expenses():
    try:
        expenses = await repo.get_expenses()
        return JSONResponse(
            status_code=200,
            content={"message": "Expenses fetched successfully", "success": True, "data": expenses}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to fetch expenses: {str(e)}", "success": False}
        )

@router.get("/{expense_id}")
async def get_expense(expense_id: str):
    try:
        expense = await repo.get_expense(expense_id)
        if not expense:
            return JSONResponse(
                status_code=404,
                content={"message": "Expense not found", "success": False}
            )
        return JSONResponse(
            status_code=200,
            content={"message": "Expense fetched successfully", "success": True, "data": expense}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to fetch expense: {str(e)}", "success": False}
        )

@router.put("/update/{expense_id}")
async def update_expense(
    expense_id: str,
    expense_category_id: Optional[str] = Form(None),
    amount: Optional[float] = Form(None),
    purpose: Optional[str] = Form(None),
    payment_mode: Optional[str] = Form(None),
    date: Optional[str] = Form(None),
    attachment: UploadFile = File(None)
):
    try:
        attachment_path = None
        if attachment:
            attachment_path = await save_file(attachment, "attachments")

        expense_update_data = ExpenseUpdate(
            expense_category_id=expense_category_id,
            amount=amount,
            purpose=purpose,
            payment_mode=payment_mode,
            date=date
        )

        updated_expense = await repo.update_expense(expense_id, expense_update_data, attachment_path)
        if not updated_expense:
            return JSONResponse(
                status_code=404,
                content={"message": "Expense not found", "success": False}
            )
        return JSONResponse(
            status_code=200,
            content={"message": "Expense updated successfully", "success": True, "data": updated_expense}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to update expense: {str(e)}", "success": False}
        )

@router.delete("/delete/{expense_id}")
async def delete_expense(expense_id: str):
    try:
        # Check if exists to maybe delete file?
        # Skipping file deletion for now to keep it simple unless requested, or if save_file/delete_file logic is robust.
        success = await repo.delete_expense(expense_id)
        if not success:
            return JSONResponse(
                status_code=404,
                content={"message": "Expense not found", "success": False}
            )
        return JSONResponse(
            status_code=200,
            content={"message": "Expense deleted successfully", "success": True}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to delete expense: {str(e)}", "success": False}
        )
