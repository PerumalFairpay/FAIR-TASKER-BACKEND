from datetime import datetime, timedelta
from jose import jwt, JWTError
from fastapi import HTTPException, Cookie, Depends
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

async def verify_token(token: str = Cookie(None)):
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
        user = await users_collection.find_one({"_id": ObjectId(user_id)})
    except:
        raise HTTPException(status_code=401, detail="Invalid user ID format")
        
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    # Fetch role permissions
    role_name = user.get("role", "employee")
    user["role"] = role_name
    role_data = await roles_collection.find_one({"name": role_name})
    
    permissions = []
    if role_data and "permissions" in role_data:
        perm_ids = role_data["permissions"]
        # Convert string IDs to ObjectIds if they are valid
        valid_ids = [ObjectId(pid) for pid in perm_ids if ObjectId.is_valid(pid)]
        if valid_ids:
            async for p in permissions_collection.find({"_id": {"$in": valid_ids}}):
                permissions.append(p.get("slug"))
    
    user["permissions"] = permissions
    
    user["id"] = str(user.pop("_id"))
    return user

def require_permission(permission: str):
    async def _has_permission(current_user: dict = Depends(get_current_user)):
        # Admin has all permissions
        if current_user.get("role") == "admin":
            return current_user
            
        if permission not in current_user.get("permissions", []):
            raise HTTPException(
                status_code=403, 
                detail=f"Missing required permission: {permission}"
            )
        return current_user
    return _has_permission
