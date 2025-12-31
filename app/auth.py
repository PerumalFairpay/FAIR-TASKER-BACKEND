from datetime import datetime, timedelta
from jose import jwt, JWTError
from fastapi import HTTPException, Cookie, Depends
from app.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from typing import Optional
from app.database import users_collection
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
    encoded = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded

def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
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
    
    user["id"] = str(user.pop("_id"))
    return user
