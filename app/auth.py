from datetime import datetime, timedelta
from jose import jwt, JWTError
from fastapi import HTTPException, Cookie, Depends, Request
from app.core.config import JWT_SECRET, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from typing import Optional
from app.database import users_collection, roles_collection, permissions_collection
from bson import ObjectId

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    # Ensure ID is a string and handle both _id and id
    if "_id" in to_encode:
        to_encode["id"] = str(to_encode.pop("_id"))
    elif "id" in to_encode:
        to_encode["id"] = str(to_encode["id"])
    
    # Remove potentially un-serializable fields
    for key in list(to_encode.keys()):
        if isinstance(to_encode[key], datetime):
            to_encode[key] = to_encode[key].isoformat()
        elif isinstance(to_encode[key], ObjectId):
            to_encode[key] = str(to_encode[key])
            
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded

def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        return None

async def verify_token(token: Optional[str] = Cookie(None)) -> dict:
    if not token:
        raise HTTPException(status_code=401, detail="Authentication token required")
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload

async def get_current_user(token: dict = Depends(verify_token)):
    user_id = token.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    
    try:
        user = await users_collection.find_one({"_id": ObjectId(user_id), "is_deleted": {"$ne": True}})
    except:
        raise HTTPException(status_code=401, detail="Invalid user ID format")
        
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    # Fetch role details and permissions
    role_id = user.get("role_id")
    role_name = user.get("role")
    role_data = None

    if role_id and ObjectId.is_valid(str(role_id)):
        role_data = await roles_collection.find_one({"_id": ObjectId(str(role_id)), "is_deleted": {"$ne": True}})
    
    if not role_data and role_name and isinstance(role_name, str):
        role_name_clean = role_name.strip()
        role_data = await roles_collection.find_one({
            "name": {"$regex": f"^{role_name_clean}$", "$options": "i"},
            "is_deleted": {"$ne": True}
        })

    # Prepare structured role object
    if role_data:
        resolved_role_name = role_data.get("name", "employee").lower()
        role_obj = {
            "id": str(role_data["_id"]),
            "name": role_data.get("name", resolved_role_name),
            "description": role_data.get("description", "")
        }
    else:
        resolved_role_name = str(role_name).lower() if isinstance(role_name, str) else "employee"
        role_obj = {
            "id": str(role_id) if role_id else "",
            "name": resolved_role_name,
            "description": ""
        }

    user["role_id"] = role_obj["id"]
    user["role"] = resolved_role_name
    user["role_details"] = role_obj
    
    # Merge Role IDs and User IDs
    all_perm_ids = set()
    
    # 1. Add Role IDs
    if role_data and "permissions" in role_data:
        all_perm_ids.update(role_data["permissions"])
        
    # 2. Add User Direct IDs
    if "permissions" in user and isinstance(user["permissions"], list):
        all_perm_ids.update(user["permissions"])
        
    # Convert all valid ObjectIds
    valid_ids = []
    for pid in all_perm_ids:
        if isinstance(pid, ObjectId):
            valid_ids.append(pid)
        elif ObjectId.is_valid(str(pid)):
            valid_ids.append(ObjectId(str(pid)))
            
    # Resolve to Slugs
    permissions = []
    if valid_ids:
        async for p in permissions_collection.find({"_id": {"$in": valid_ids}}):
            permissions.append(p.get("slug"))
            
    user["permissions"] = list(set(permissions))
    
    user["id"] = str(user.pop("_id"))
    return user

def require_permission(permission: str):
    async def _has_permission(current_user: dict = Depends(get_current_user)):
        # Admin has all permissions
        role_val = current_user.get("role")
        user_role_str = role_val.get("name", "").lower() if isinstance(role_val, dict) else str(role_val or "").lower()
        if user_role_str == "admin":
            return current_user
            
        if permission not in current_user.get("permissions", []):
            raise HTTPException(
                status_code=403, 
                detail=f"Missing required permission: {permission}"
            )
        return current_user
    return _has_permission
