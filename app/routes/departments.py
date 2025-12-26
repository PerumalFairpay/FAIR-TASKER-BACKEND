from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from app.database import departments_collection
from app.models import DepartmentCreate, DepartmentResponse, DepartmentUpdate, UserResponse
from app.dependencies import get_current_admin
from bson import ObjectId

router = APIRouter()

@router.post("/", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
async def create_department(dept: DepartmentCreate, current_admin: UserResponse = Depends(get_current_admin)):
    existing_dept = await departments_collection.find_one({"name": dept.name})
    if existing_dept:
        raise HTTPException(status_code=400, detail="Department with this name already exists")
    
    dept_dict = dept.dict()
    new_dept = await departments_collection.insert_one(dept_dict)
    created_dept = await departments_collection.find_one({"_id": new_dept.inserted_id})
    
    return DepartmentResponse(id=str(created_dept["_id"]), **dept_dict)

@router.get("/", response_model=List[DepartmentResponse])
async def read_departments():
    # Public endpoint so registration page can fetch departments
    departments = []
    cursor = departments_collection.find({})
    async for document in cursor:
        departments.append(DepartmentResponse(id=str(document["_id"]), **document))
    return departments

@router.get("/{dept_id}", response_model=DepartmentResponse)
async def read_department(dept_id: str):
    if not ObjectId.is_valid(dept_id):
        raise HTTPException(status_code=400, detail="Invalid department ID")
        
    dept = await departments_collection.find_one({"_id": ObjectId(dept_id)})
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
        
    return DepartmentResponse(id=str(dept["_id"]), **dept)

@router.put("/{dept_id}", response_model=DepartmentResponse)
async def update_department(dept_id: str, dept_update: DepartmentUpdate, current_admin: UserResponse = Depends(get_current_admin)):
    if not ObjectId.is_valid(dept_id):
        raise HTTPException(status_code=400, detail="Invalid department ID")
    
    update_data = {k: v for k, v in dept_update.dict().items() if v is not None}
    
    if not update_data:
         raise HTTPException(status_code=400, detail="No valid fields to update")

    result = await departments_collection.update_one(
        {"_id": ObjectId(dept_id)}, 
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Department not found")
        
    updated_dept = await departments_collection.find_one({"_id": ObjectId(dept_id)})
    return DepartmentResponse(id=str(updated_dept["_id"]), **updated_dept)

@router.delete("/{dept_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_department(dept_id: str, current_admin: UserResponse = Depends(get_current_admin)):
    if not ObjectId.is_valid(dept_id):
        raise HTTPException(status_code=400, detail="Invalid department ID")
        
    result = await departments_collection.delete_one({"_id": ObjectId(dept_id)})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Department not found")
    return
