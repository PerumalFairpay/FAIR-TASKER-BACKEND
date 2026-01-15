from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)

from bson import ObjectId
from datetime import datetime

def normalize(data):
    """
    Recursively converts _id to id, ObjectId to str, and datetime to isoformat 
    so that the data can be JSON serialized.
    """
    if isinstance(data, list):
        return [normalize(item) for item in data]
    
    if isinstance(data, dict):
        new_dict = {}
        # Special handling for _id -> id at the top level of the dict
        # but also handles nested _id if they exist
        for k, v in data.items():
            key = "id" if k == "_id" else k
            new_dict[key] = normalize(v)
        return new_dict
    
    if isinstance(data, ObjectId):
        return str(data)
    
    if isinstance(data, datetime):
        return data.isoformat()
    
    return data
