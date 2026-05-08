from datetime import datetime
from bson import ObjectId
from app.database import ai_chat_sessions_collection, ai_chat_messages_collection
from typing import List, Optional

async def create_chat_session(user_id: str, title: str) -> str:
    session = {
        "user_id": user_id,
        "title": title[:60],
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "message_count": 0
    }
    result = await ai_chat_sessions_collection.insert_one(session)
    return str(result.inserted_id)

async def add_chat_message(session_id: str, role: str, content: str):
    message = {
        "session_id": session_id,
        "role": role,
        "content": content,
        "created_at": datetime.utcnow()
    }
    await ai_chat_messages_collection.insert_one(message)
    # Increment message count and update timestamp
    await ai_chat_sessions_collection.update_one(
        {"_id": ObjectId(session_id)},
        {
            "$inc": {"message_count": 1},
            "$set": {"updated_at": datetime.utcnow()}
        }
    )

async def get_chat_sessions(user_id: str, skip: int = 0, limit: int = 50) -> List[dict]:
    cursor = ai_chat_sessions_collection.find({"user_id": user_id}).sort("updated_at", -1).skip(skip).limit(limit)
    sessions = []
    async for session in cursor:
        session["id"] = str(session["_id"])
        sessions.append(session)
    return sessions

async def get_chat_messages(session_id: str, user_id: str) -> List[dict]:
    # Security check: ensure session belongs to user
    session = await ai_chat_sessions_collection.find_one({"_id": ObjectId(session_id), "user_id": user_id})
    if not session:
        return []
    
    cursor = ai_chat_messages_collection.find({"session_id": session_id}).sort("created_at", 1)
    messages = []
    async for msg in cursor:
        msg["id"] = str(msg["_id"])
        messages.append(msg)
    return messages

async def delete_chat_session(session_id: str, user_id: str) -> bool:
    # Security check: ensure session belongs to user
    result = await ai_chat_sessions_collection.delete_one({"_id": ObjectId(session_id), "user_id": user_id})
    if result.deleted_count > 0:
        # Delete associated messages
        await ai_chat_messages_collection.delete_many({"session_id": session_id})
        return True
    return False

async def clear_all_chat_history(user_id: str):
    # Find all sessions for user
    cursor = ai_chat_sessions_collection.find({"user_id": user_id}, {"_id": 1})
    session_ids = [str(s["_id"]) async for s in cursor]
    
    if session_ids:
        await ai_chat_sessions_collection.delete_many({"user_id": user_id})
        await ai_chat_messages_collection.delete_many({"session_id": {"$in": session_ids}})
