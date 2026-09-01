---
name: backend-service-refactoring
description: >-
  Standardized guidelines and step-by-step procedure for refactoring FastAPI backend routes into a modular, service-oriented architecture (like in FLEETGLIDE-AI-BACKEND) with domain services under app/services/api/, soft deletion, and standardized JSON responses.
---

# Backend Service Layer Architecture & Refactoring Guide

This skill guides the agent and developers on how to design, create, and refactor routes and business logic in the backend into a modular **Service-Oriented Architecture** (inspired by `FLEETGLIDE-AI-BACKEND`).

---

## 1. Core Architectural Principles

1. **Routes Layer (`app/routes/<domain>.py`)**:
   - **Role**: Thin REST Controller layer.
   - **Responsibilities**:
     - Handle HTTP method, path, status codes, query/form/body parameter extraction.
     - Enforce authentication (`Depends(verify_token)`) and permissions (`Depends(require_permission(...))`).
     - Delegate all domain business logic, data formatting, and database queries directly to the Service Layer (`DomainService`).
     - Return responses solely via `success_response(...)` and `error_response(...)` helpers from `app.helper.response_helper`.
     - In `delete` endpoints, always return `data=[]` in the `success_response`.

2. **Services Layer (`app/services/api/<domain>.py`)**:
   - **Role**: Domain Business Logic Layer.
   - **Responsibilities**:
     - Implement clean static methods on domain service classes (e.g., `HolidayService`, `ProjectService`, `SettingsService`).
     - Validate input data, `ObjectId` validity, and entity existence.
     - Interact directly with MongoDB collection instances exported from `app.database`.
     - Implement **Soft Delete** (`is_deleted: True`, `deleted_at: datetime.utcnow()`) across records.
     - Exclude soft-deleted items across find/get/update queries via `{"is_deleted": {"$ne": True}}`.
     - Return standardized `Tuple[Optional[T], Optional[str]]` (i.e. `(data, error)` tuples).

3. **Database Layer (`app/database.py`)**:
   - Centralize and export MongoDB collections:
     ```python
     holidays_collection = db["holidays"]
     projects_collection = db["projects"]
     tasks_collection = db["tasks"]
     ...
     ```

4. **Service Exports (`app/services/api/__init__.py`)**:
   - Re-export all service classes so other modules or background services can import cleanly:
     ```python
     from app.services.api.settings import SettingsService
     from app.services.api.holiday import HolidayService
     from app.services.api.project import ProjectService
     ```

---

## 2. Standard Service Template

Create `app/services/api/<domain>.py` with the following structure:

```python
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from bson import ObjectId
from app.database import <domain>_collection
from app.models import <Domain>Create, <Domain>Update
from app.utils import normalize
import traceback


class <Domain>Service:

    @staticmethod
    async def create(data_in: <Domain>Create) -> Tuple[Optional[dict], Optional[str]]:
        try:
            data = data_in.dict()
            data["is_deleted"] = False
            data["deleted_at"] = None
            data["created_at"] = datetime.utcnow()
            result = await <domain>_collection.insert_one(data)
            data["id"] = str(result.inserted_id)
            return normalize(data), None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def list() -> Tuple[Optional[List[dict]], Optional[str]]:
        try:
            items = await <domain>_collection.find(
                {"is_deleted": {"$ne": True}}
            ).to_list(length=None)
            return [normalize(item) for item in items], None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def get(item_id: str) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(item_id):
                return None, "Invalid ID format"
            item = await <domain>_collection.find_one({
                "_id": ObjectId(item_id),
                "is_deleted": {"$ne": True}
            })
            if not item:
                return None, "<Domain> not found"
            return normalize(item), None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def update(item_id: str, data_in: <Domain>Update) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(item_id):
                return None, "Invalid ID format"

            update_data = {k: v for k, v in data_in.dict().items() if v is not None}
            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                result = await <domain>_collection.update_one(
                    {"_id": ObjectId(item_id), "is_deleted": {"$ne": True}},
                    {"$set": update_data}
                )
                if result.matched_count == 0:
                    return None, "<Domain> not found"

            return await <Domain>Service.get(item_id)
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def delete(item_id: str) -> Tuple[bool, Optional[str]]:
        try:
            if not ObjectId.is_valid(item_id):
                return False, "Invalid ID format"

            result = await <domain>_collection.update_one(
                {"_id": ObjectId(item_id), "is_deleted": {"$ne": True}},
                {"$set": {"is_deleted": True, "deleted_at": datetime.utcnow()}}
            )
            if result.matched_count == 0:
                return False, "<Domain> not found"
            return True, None
        except Exception as e:
            traceback.print_exc()
            return False, str(e)
```

---

## 3. Standard Route Template

Create or refactor `app/routes/<domain>.py`:

```python
from fastapi import APIRouter, Depends
from app.models import <Domain>Create, <Domain>Update
from app.services.api.<domain> import <Domain>Service
from app.helper.response_helper import success_response, error_response
from app.auth import verify_token, require_permission

router = APIRouter(prefix="/<domain>s", tags=["<domain>s"], dependencies=[Depends(verify_token)])

@router.post("/create", dependencies=[Depends(require_permission("<domain>:submit"))])
async def create_<domain>(data_in: <Domain>Create):
    data, error = await <Domain>Service.create(data_in)
    if error:
        return error_response(message=f"Failed to create <domain>: {error}", status_code=500)
    return success_response(message="<Domain> created successfully", data=data, status_code=201)

@router.get("/all", dependencies=[Depends(require_permission("<domain>:view"))])
async def get_<domain>s():
    data, error = await <Domain>Service.list()
    if error:
        return error_response(message=f"Failed to fetch <domain>s: {error}", status_code=500)
    return success_response(message="<Domain>s fetched successfully", data=data)

@router.get("/{item_id}", dependencies=[Depends(require_permission("<domain>:view"))])
async def get_<domain>(item_id: str):
    data, error = await <Domain>Service.get(item_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="<Domain> fetched successfully", data=data)

@router.put("/update/{item_id}", dependencies=[Depends(require_permission("<domain>:submit"))])
async def update_<domain>(item_id: str, data_in: <Domain>Update):
    data, error = await <Domain>Service.update(item_id, data_in)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="<Domain> updated successfully", data=data)

@router.delete("/delete/{item_id}", dependencies=[Depends(require_permission("<domain>:submit"))])
async def delete_<domain>(item_id: str):
    success, error = await <Domain>Service.delete(item_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="<Domain> deleted successfully", data=[])
```

---

## 4. Migration Checklist for New Endpoints

When refactoring an existing route:
- [ ] 1. Identify existing queries and transformations in `app/crud/repository.py` for this domain.
- [ ] 2. Ensure target collection is exported in `app/database.py`.
- [ ] 3. Create `app/services/api/<domain>.py` with `<Domain>Service` methods returning `Tuple[data, error]`.
- [ ] 4. Include `is_deleted` filter and soft delete handling.
- [ ] 5. Export `<Domain>Service` in `app/services/api/__init__.py`.
- [ ] 6. Refactor `app/routes/<domain>.py` to call `<Domain>Service` and use `success_response` / `error_response`.
- [ ] 7. Ensure `delete` routes return `data=[]`.
- [ ] 8. Verify the contract with the frontend to ensure no breaking changes.
