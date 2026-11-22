from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict, Union
from datetime import datetime

class ExpenseCategoryBase(BaseModel):
    name: str
    description: Optional[str] = None
    parent_id: Optional[Union[str, int]] = None

class ExpenseCategoryCreate(ExpenseCategoryBase):
    pass

class ExpenseCategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[Union[str, int]] = None

class ExpenseCategoryResponse(ExpenseCategoryBase):
    id: str

    class Config:
        from_attributes = True

class ExpenseBase(BaseModel):
    expense_category_id: str
    expense_subcategory_id: Optional[str] = None
    amount: float
    purpose: str
    payment_mode: str
    date: str
    attachment: Optional[str] = None
    file_type: Optional[str] = None

class ExpenseCreate(ExpenseBase):
    pass

class ExpenseUpdate(BaseModel):
    expense_category_id: Optional[str] = None
    expense_subcategory_id: Optional[str] = None
    amount: Optional[float] = None
    purpose: Optional[str] = None
    payment_mode: Optional[str] = None
    date: Optional[str] = None
    attachment: Optional[str] = None
    file_type: Optional[str] = None

class ExpenseResponse(ExpenseBase):
    id: str
    category_name: Optional[str] = None
    subcategory_name: Optional[str] = None

    class Config:
        from_attributes = True
