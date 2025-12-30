from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)

from bson import ObjectId
from datetime import datetime

def normalize(doc: dict) -> dict:
    """Converts _id and any ObjectId fields to str so Pydantic/JSON can serialize them."""
    if not doc:
        return doc
    new_doc = {}
    for k, v in doc.items():
        if isinstance(v, ObjectId):
            new_doc[k] = str(v)
        elif isinstance(v, list):
            new_doc[k] = [str(x) if isinstance(x, ObjectId) else x for x in v]
        elif isinstance(v, dict):
            new_doc[k] = normalize(v)
        elif isinstance(v, datetime):
            new_doc[k] = v.isoformat()
        else:
            new_doc[k] = v
    if "_id" in new_doc:
        new_doc["id"] = new_doc.pop("_id")
    return new_doc
