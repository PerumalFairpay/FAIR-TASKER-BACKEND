from typing import Dict, Any, List, Optional, Tuple, AsyncGenerator
from datetime import datetime
from bson import ObjectId
from app.database import chat_sessions_collection, chat_messages_collection
from app.services.ai_service import chat_stream
from app.utils import normalize
import traceback


class AIService:

    @staticmethod
    async def create_session(user_id: str, title: str = "New Chat") -> Tuple[Optional[dict], Optional[str]]:
        try:
            session_data = {
                "user_id": user_id,
                "title": title,
                "is_deleted": False,
                "deleted_at": None,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            result = await chat_sessions_collection.insert_one(session_data)
            session_data["id"] = str(result.inserted_id)
            return normalize(session_data), None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def get_sessions(user_id: str) -> Tuple[Optional[List[dict]], Optional[str]]:
        try:
            sessions = await chat_sessions_collection.find({
                "user_id": user_id,
                "is_deleted": {"$ne": True}
            }).sort("updated_at", -1).to_list(length=None)

            result = []
            for session in sessions:
                norm_session = normalize(session)
                last_msg = await chat_messages_collection.find_one(
                    {"session_id": norm_session["id"]},
                    sort=[("created_at", -1)]
                )
                if last_msg:
                    norm_session["last_message"] = last_msg.get("content", "")
                result.append(norm_session)

            return result, None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def get_messages(session_id: str) -> Tuple[Optional[List[dict]], Optional[str]]:
        try:
            messages = await chat_messages_collection.find({"session_id": session_id}).sort("created_at", 1).to_list(length=None)
            return [normalize(msg) for msg in messages], None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def create_message(session_id: str, role: str, content: str) -> Tuple[Optional[dict], Optional[str]]:
        try:
            message_data = {
                "session_id": session_id,
                "role": role,
                "content": content,
                "created_at": datetime.utcnow()
            }
            result = await chat_messages_collection.insert_one(message_data)

            # Update session's updated_at
            if ObjectId.is_valid(session_id):
                await chat_sessions_collection.update_one(
                    {"_id": ObjectId(session_id)},
                    {"$set": {"updated_at": datetime.utcnow()}}
                )

            message_data["id"] = str(result.inserted_id)
            return normalize(message_data), None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def update_session_title(session_id: str, title: str) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(session_id):
                return None, "Invalid session ID"

            await chat_sessions_collection.update_one(
                {"_id": ObjectId(session_id), "is_deleted": {"$ne": True}},
                {"$set": {"title": title, "updated_at": datetime.utcnow()}}
            )
            session = await chat_sessions_collection.find_one({"_id": ObjectId(session_id)})
            if not session:
                return None, "Chat session not found"
            return normalize(session), None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def delete_session(session_id: str) -> Tuple[bool, Optional[str]]:
        try:
            if not ObjectId.is_valid(session_id):
                return False, "Invalid session ID"

            # Soft delete session
            result = await chat_sessions_collection.update_one(
                {"_id": ObjectId(session_id), "is_deleted": {"$ne": True}},
                {"$set": {"is_deleted": True, "deleted_at": datetime.utcnow()}}
            )
            if result.matched_count == 0:
                return False, "Chat session not found"

            # Delete / Clean associated messages
            await chat_messages_collection.delete_many({"session_id": session_id})
            return True, None
        except Exception as e:
            traceback.print_exc()
            return False, str(e)

    @staticmethod
    async def stream_chat(
        query: str,
        user_id: str,
        session_id: Optional[str],
        current_user: dict
    ) -> AsyncGenerator[str, None]:
        """
        Handles session creation, history retrieval, streaming output,
        and persisting user + assistant messages.
        """
        active_session_id = session_id
        is_new_session = False
        if not active_session_id:
            title = (query[:30] + '...') if len(query) > 30 else query
            session, err = await AIService.create_session(user_id, title)
            if session:
                active_session_id = session["id"]
                is_new_session = True

        # Fetch history
        db_messages, _ = await AIService.get_messages(active_session_id)
        history = [{"role": msg["role"], "content": msg["content"]} for msg in (db_messages or [])]

        # Save user message
        await AIService.create_message(active_session_id, "user", query)

        full_response = ""
        if is_new_session:
            yield f"__SESSION_ID__: {active_session_id}\n"

        async for chunk in chat_stream(query, history, current_user):
            full_response += chunk
            yield chunk

        if full_response.strip():
            await AIService.create_message(active_session_id, "assistant", full_response)
