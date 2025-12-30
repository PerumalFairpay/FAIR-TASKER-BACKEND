from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import JSONResponse
from app.crud.repository import repository as repo
from app.models import ExpenseCategoryCreate, ExpenseCategoryUpdate
from typing import List

router = APIRouter(prefix="/expense-categories", tags=["expense-categories"])

@router.post("/create")
async def create_category(category: ExpenseCategoryCreate):
    try:
        new_category = await repo.create_expense_category(category)
        return JSONResponse(
            status_code=201,
            content={"message": "Category created successfully", "success": True, "data": new_category}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to create category: {str(e)}", "success": False}
        )

@router.get("/all")
async def get_categories():
    try:
        categories = await repo.get_expense_categories()
        return JSONResponse(
            status_code=200,
            content={"message": "Categories fetched successfully", "success": True, "data": categories}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to fetch categories: {str(e)}", "success": False}
        )

@router.get("/{category_id}")
async def get_category(category_id: str):
    try:
        category = await repo.get_expense_category(category_id)
        if not category:
            return JSONResponse(
                status_code=404,
                content={"message": "Category not found", "success": False}
            )
        return JSONResponse(
            status_code=200,
            content={"message": "Category fetched successfully", "success": True, "data": category}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to fetch category: {str(e)}", "success": False}
        )

@router.put("/update/{category_id}")
async def update_category(category_id: str, category: ExpenseCategoryUpdate):
    try:
        updated_category = await repo.update_expense_category(category_id, category)
        if not updated_category:
            return JSONResponse(
                status_code=404,
                content={"message": "Category not found", "success": False}
            )
        return JSONResponse(
            status_code=200,
            content={"message": "Category updated successfully", "success": True, "data": updated_category}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to update category: {str(e)}", "success": False}
        )

@router.delete("/delete/{category_id}")
async def delete_category(category_id: str):
    try:
        success = await repo.delete_expense_category(category_id)
        if not success:
            return JSONResponse(
                status_code=404,
                content={"message": "Category not found", "success": False}
            )
        return JSONResponse(
            status_code=200,
            content={"message": "Category deleted successfully", "success": True}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to delete category: {str(e)}", "success": False}
        )
