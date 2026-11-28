import asyncio
import logging
import re
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from bson import ObjectId

from app.database import employees_collection, notifications_collection, roles_collection, users_collection
from app.services.push_notification_service import PushNotificationService

logger = logging.getLogger("notification_helper")


class NotificationHelper:
    """
    Unified helper to dispatch in-app notifications (MongoDB)
    and OneSignal push notifications without blocking HTTP responses.
    """

    @classmethod
    def _dispatch_task(cls, coro) -> None:
        """Schedules an async coroutine on the active event loop or a daemon thread."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(coro)
        except RuntimeError:
            threading.Thread(target=asyncio.run, args=(coro,), daemon=True).start()

    @classmethod
    def _truncate_text(cls, text: Optional[str], max_length: int = 160) -> str:
        if not text:
            return ""
        text = text.strip()
        return text if len(text) <= max_length else text[: max_length - 3] + "..."

    @classmethod
    async def get_user_ids_by_roles(cls, roles: List[str]) -> List[str]:
        """Fetches active, non-deleted user IDs matching any of the given role names."""
        clean_roles = [r.strip() for r in roles if r and r.strip()]
        if not clean_roles:
            return []

        role_patterns = [re.compile(f"^{re.escape(r)}$", re.IGNORECASE) for r in clean_roles]
        role_cursor = roles_collection.find(
            {"name": {"$in": role_patterns}, "is_deleted": {"$ne": True}},
            {"_id": 1},
        )
        role_oids: List[ObjectId] = []
        role_id_strs: List[str] = []
        async for role_doc in role_cursor:
            role_oids.append(role_doc["_id"])
            role_id_strs.append(str(role_doc["_id"]))

        or_conditions: List[Dict[str, Any]] = [{"role": {"$in": role_patterns}}]
        if role_id_strs:
            or_conditions.append({"role_id": {"$in": role_id_strs + role_oids}})

        user_cursor = users_collection.find(
            {
                "is_deleted": {"$ne": True},
                "is_active": {"$ne": False},
                "$or": or_conditions,
            },
            {"_id": 1},
        )
        return [str(doc["_id"]) async for doc in user_cursor]

    @classmethod
    async def get_user_id_for_employee(
        cls,
        employee_id: Optional[str] = None,
        email: Optional[str] = None,
    ) -> Optional[str]:
        """Resolves the active user_id for an employee via user_id or email."""
        emp_doc = None
        if employee_id and ObjectId.is_valid(str(employee_id)):
            emp_doc = await employees_collection.find_one(
                {"_id": ObjectId(str(employee_id)), "is_deleted": {"$ne": True}},
                {"user_id": 1, "email": 1},
            )

        resolved_user_id = emp_doc.get("user_id") if emp_doc else None
        if resolved_user_id:
            return str(resolved_user_id)

        resolved_email = email or (emp_doc.get("email") if emp_doc else None)
        if not resolved_email:
            return None

        user_doc = await users_collection.find_one(
            {
                "is_deleted": {"$ne": True},
                "is_active": {"$ne": False},
                "email": re.compile(f"^{re.escape(resolved_email.strip())}$", re.IGNORECASE),
            },
            {"_id": 1},
        )
        return str(user_doc["_id"]) if user_doc else None

    @classmethod
    def trigger_employee_notification(
        cls,
        title: str,
        body: str,
        employee_id: Optional[str] = None,
        email: Optional[str] = None,
        notification_type: str = "general",
        data: Optional[Dict[str, Any]] = None,
        url: Optional[str] = None,
        image_url: Optional[str] = None,
        send_push: bool = True,
        save_in_app: bool = True,
    ) -> None:
        """Fire-and-forget notification dispatch to a single employee."""
        cls._dispatch_task(
            cls.notify_employee(
                employee_id=employee_id,
                email=email,
                title=title,
                body=body,
                notification_type=notification_type,
                data=data,
                url=url,
                image_url=image_url,
                send_push=send_push,
                save_in_app=save_in_app,
            )
        )

    @classmethod
    async def notify_employee(
        cls,
        title: str,
        body: str,
        employee_id: Optional[str] = None,
        email: Optional[str] = None,
        notification_type: str = "general",
        data: Optional[Dict[str, Any]] = None,
        url: Optional[str] = None,
        image_url: Optional[str] = None,
        send_push: bool = True,
        save_in_app: bool = True,
    ) -> None:
        """Resolves an employee's user account and sends them a notification."""
        try:
            user_id = await cls.get_user_id_for_employee(
                employee_id=employee_id,
                email=email,
            )
            if user_id:
                await cls.notify_users(
                    user_ids=[user_id],
                    title=title,
                    body=body,
                    notification_type=notification_type,
                    data=data,
                    url=url,
                    image_url=image_url,
                    send_push=send_push,
                    save_in_app=save_in_app,
                )
        except Exception as e:
            logger.error(f"Failed to notify employee {employee_id or email}: {e}", exc_info=True)

    @classmethod
    def trigger_user_notification(
        cls,
        user_ids: List[Union[str, int]],
        title: str,
        body: str,
        notification_type: str = "general",
        data: Optional[Dict[str, Any]] = None,
        url: Optional[str] = None,
        image_url: Optional[str] = None,
        send_push: bool = True,
        save_in_app: bool = True,
    ) -> None:
        """Fire-and-forget notification dispatch to specific user IDs."""
        if not user_ids:
            return
        cls._dispatch_task(
            cls.notify_users(
                user_ids=user_ids,
                title=title,
                body=body,
                notification_type=notification_type,
                data=data,
                url=url,
                image_url=image_url,
                send_push=send_push,
                save_in_app=save_in_app,
            )
        )

    @classmethod
    def trigger_role_notification(
        cls,
        roles: List[str],
        title: str,
        body: str,
        notification_type: str = "general",
        data: Optional[Dict[str, Any]] = None,
        url: Optional[str] = None,
        image_url: Optional[str] = None,
        send_push: bool = True,
        save_in_app: bool = True,
    ) -> None:
        """Fire-and-forget notification dispatch to all active users with the given roles."""
        if not roles:
            return
        cls._dispatch_task(
            cls.notify_roles(
                roles=roles,
                title=title,
                body=body,
                notification_type=notification_type,
                data=data,
                url=url,
                image_url=image_url,
                send_push=send_push,
                save_in_app=save_in_app,
            )
        )

    @classmethod
    async def notify_roles(
        cls,
        roles: List[str],
        title: str,
        body: str,
        notification_type: str = "general",
        data: Optional[Dict[str, Any]] = None,
        url: Optional[str] = None,
        image_url: Optional[str] = None,
        send_push: bool = True,
        save_in_app: bool = True,
    ) -> None:
        """Resolves active users for the given roles and sends them notifications."""
        try:
            user_ids = await cls.get_user_ids_by_roles(roles)
            if user_ids:
                await cls.notify_users(
                    user_ids=user_ids,
                    title=title,
                    body=body,
                    notification_type=notification_type,
                    data=data,
                    url=url,
                    image_url=image_url,
                    send_push=send_push,
                    save_in_app=save_in_app,
                )
        except Exception as e:
            logger.error(f"Failed to notify roles {roles}: {e}", exc_info=True)

    @classmethod
    async def notify_users(
        cls,
        user_ids: List[Union[str, int]],
        title: str,
        body: str,
        notification_type: str = "general",
        data: Optional[Dict[str, Any]] = None,
        url: Optional[str] = None,
        image_url: Optional[str] = None,
        send_push: bool = True,
        save_in_app: bool = True,
    ) -> None:
        """Persists in-app notifications in MongoDB and sends OneSignal push."""
        if not user_ids:
            return

        string_ids = list({str(uid) for uid in user_ids if uid is not None and str(uid).strip()})
        if not string_ids:
            return

        now = datetime.utcnow()
        payload_data = dict(data) if data else {}
        payload_data.setdefault("type", notification_type)
        if url:
            payload_data.setdefault("url", url)

        if save_in_app:
            try:
                docs = [
                    {
                        "user_id": uid,
                        "title": title,
                        "body": body,
                        "type": notification_type,
                        "data": payload_data,
                        "url": url,
                        "image_url": image_url,
                        "is_read": False,
                        "read_at": None,
                        "is_deleted": False,
                        "created_at": now,
                        "updated_at": now,
                    }
                    for uid in string_ids
                ]
                await notifications_collection.insert_many(docs)
            except Exception as e:
                logger.error(f"Failed to save in-app notifications: {e}", exc_info=True)

        if send_push:
            try:
                await PushNotificationService.send_to_users(
                    user_ids=string_ids,
                    title=title,
                    body=cls._truncate_text(body, 200),
                    data=payload_data,
                    url=url,
                    image_url=image_url,
                )
            except Exception as e:
                logger.error(f"Failed to send OneSignal push notification: {e}", exc_info=True)

    @classmethod
    async def notify_all_active_users(
        cls,
        title: str,
        body: str,
        notification_type: str = "broadcast",
        data: Optional[Dict[str, Any]] = None,
        url: Optional[str] = None,
        image_url: Optional[str] = None,
        send_push: bool = True,
        save_in_app: bool = True,
    ) -> None:
        """Broadcasts a notification to all active, non-deleted users."""
        try:
            cursor = users_collection.find(
                {"is_deleted": {"$ne": True}, "is_active": {"$ne": False}},
                {"_id": 1},
            )
            user_ids = [str(doc["_id"]) async for doc in cursor]
            if user_ids:
                await cls.notify_users(
                    user_ids=user_ids,
                    title=title,
                    body=body,
                    notification_type=notification_type,
                    data=data,
                    url=url,
                    image_url=image_url,
                    send_push=send_push,
                    save_in_app=save_in_app,
                )
        except Exception as e:
            logger.error(f"Failed to broadcast notification to active users: {e}", exc_info=True)
