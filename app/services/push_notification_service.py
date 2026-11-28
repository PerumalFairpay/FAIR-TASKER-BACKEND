import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from app.core import config
from app.database import notification_logs_collection
from app.schemas.notification import PushNotificationResult

logger = logging.getLogger("push_notification_service")

# Lazy import flag for onesignal SDK to allow runtime flexibility
try:
    import onesignal
    from onesignal.api import default_api
    from onesignal.model.notification import Notification
    try:
        from onesignal.model.language_string_map import LanguageStringMap as StringMap
    except ImportError:
        try:
            from onesignal.model.string_map import StringMap
        except ImportError:
            StringMap = dict
    ONESIGNAL_SDK_AVAILABLE = True
except Exception as e:
    ONESIGNAL_SDK_AVAILABLE = False
    logger.warning(
        f"onesignal-python-api package is not available ({e}). "
        "Push notifications will run in mock/disabled mode."
    )


class PushNotificationService:
    """
    Push Notification Service wrapping the OneSignal Python SDK with MongoDB audit logging.
    Features:
      - Non-blocking async API dispatch via asyncio.to_thread()
      - OneSignal external_id alias targeting, subscription IDs, and segment/all broadcasts
      - MongoDB audit logging (notification_logs_collection)
      - Fail-open resilience (never crashes main business transactions)
      - Configurable toggle via ONESIGNAL_ENABLED
    """

    @classmethod
    def _is_configured(cls) -> bool:
        return bool(
            config.ONESIGNAL_ENABLED
            and config.ONESIGNAL_APP_ID
            and config.ONESIGNAL_REST_API_KEY
            and ONESIGNAL_SDK_AVAILABLE
        )

    @classmethod
    def _get_api_client(cls) -> Optional["default_api.DefaultApi"]:
        if not cls._is_configured():
            return None

        configuration = onesignal.Configuration(
            rest_api_key=config.ONESIGNAL_REST_API_KEY,
        )
        api_client = onesignal.ApiClient(configuration)
        return default_api.DefaultApi(api_client)

    @classmethod
    async def _log_to_db(
        cls,
        target_type: str,
        target_identifiers: Optional[Union[List[Any], str]],
        title: str,
        body: str,
        data_payload: Optional[Dict[str, Any]],
        status: str,
        notification_id: Optional[str] = None,
        recipients_count: int = 0,
        error_message: Optional[str] = None,
    ) -> Optional[str]:
        """Asynchronously records an audit log entry in MongoDB."""
        try:
            target_ids_str = (
                json.dumps(target_identifiers)
                if isinstance(target_identifiers, (list, dict))
                else (str(target_identifiers) if target_identifiers is not None else None)
            )
            data_str = json.dumps(data_payload) if data_payload else None

            doc = {
                "notification_id": notification_id,
                "target_type": target_type,
                "target_identifiers": target_ids_str,
                "title": title,
                "body": body,
                "data_payload": data_str,
                "status": status,
                "recipients_count": recipients_count,
                "error_message": error_message,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
            result = await notification_logs_collection.insert_one(doc)
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Failed to record push notification audit log to MongoDB: {e}", exc_info=True)
            return None

    @classmethod
    def _dispatch_sync(
        cls,
        notification_kwargs: Dict[str, Any],
        target_type: str,
        title: str,
        body: str,
        data_payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Synchronous internal worker that constructs and sends the OneSignal payload."""
        if not cls._is_configured():
            reason = (
                "OneSignal is disabled or credentials (ONESIGNAL_APP_ID / ONESIGNAL_REST_API_KEY) are missing."
                if ONESIGNAL_SDK_AVAILABLE
                else "onesignal-python-api SDK is not installed."
            )
            logger.info(f"Skipping push notification dispatch: {reason}")
            return {
                "success": True,
                "status": "DISABLED",
                "notification_id": "MOCK_DISPATCHED",
                "recipients": 0,
                "error": reason,
            }

        try:
            contents = StringMap(en=body)
            headings = StringMap(en=title)

            base_params: Dict[str, Any] = {
                "app_id": config.ONESIGNAL_APP_ID,
                "contents": contents,
                "headings": headings,
            }

            if data_payload:
                base_params["data"] = data_payload

            img_url = notification_kwargs.pop("image_url", None)
            if img_url and "big_picture" not in notification_kwargs:
                notification_kwargs["big_picture"] = img_url

            if notification_kwargs.get("big_picture"):
                pic = notification_kwargs["big_picture"]
                if "ios_attachments" not in notification_kwargs:
                    notification_kwargs["ios_attachments"] = {"image": pic}
                if "chrome_web_image" not in notification_kwargs:
                    notification_kwargs["chrome_web_image"] = pic

            base_params.update(notification_kwargs)
            notification = Notification(**base_params)

            client = cls._get_api_client()
            response = client.create_notification(notification)

            notification_id = getattr(response, "id", None) or ""
            recipients = getattr(response, "recipients", 0) or 0
            errors = getattr(response, "errors", None)

            status = "SENT"
            error_message = None
            if not notification_id or errors:
                error_message = (
                    str(errors)
                    if errors
                    else "No notification ID returned by OneSignal (0 active subscribers)"
                )
                if not notification_id and errors:
                    status = "FAILED"
                logger.warning(
                    f"OneSignal push warning: ID='{notification_id}', Recipients={recipients}, Errors={error_message}"
                )
            else:
                logger.info(
                    f"Push notification dispatched successfully. ID={notification_id}, "
                    f"Recipients={recipients}, Target Type={target_type}"
                )

            return {
                "success": status != "FAILED",
                "status": status,
                "notification_id": notification_id or None,
                "recipients": recipients,
                "error": error_message,
            }
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to dispatch OneSignal push notification: {error_msg}", exc_info=True)
            return {
                "success": False,
                "status": "FAILED",
                "notification_id": None,
                "recipients": 0,
                "error": error_msg,
            }

    @classmethod
    async def _dispatch_and_log(
        cls,
        notification_kwargs: Dict[str, Any],
        target_type: str,
        target_identifiers: Optional[Union[List[Any], str]],
        title: str,
        body: str,
        data_payload: Optional[Dict[str, Any]] = None,
    ) -> PushNotificationResult:
        outcome = await asyncio.to_thread(
            cls._dispatch_sync,
            notification_kwargs=notification_kwargs,
            target_type=target_type,
            title=title,
            body=body,
            data_payload=data_payload,
        )
        log_id = await cls._log_to_db(
            target_type=target_type,
            target_identifiers=target_identifiers,
            title=title,
            body=body,
            data_payload=data_payload,
            status=outcome["status"],
            notification_id=outcome["notification_id"],
            recipients_count=outcome["recipients"],
            error_message=outcome["error"],
        )
        return PushNotificationResult(
            success=outcome["success"],
            notification_id=outcome["notification_id"],
            recipients=outcome["recipients"],
            error=outcome["error"],
            log_id=log_id,
        )

    @classmethod
    async def send_to_users(
        cls,
        user_ids: List[Union[int, str]],
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        subtitle: Optional[str] = None,
        badge_count: Optional[int] = None,
        sound: Optional[str] = None,
        android_channel_id: Optional[str] = None,
        big_picture: Optional[str] = None,
        image_url: Optional[str] = None,
        image_urls: Optional[List[str]] = None,
        ios_attachments: Optional[Dict[str, str]] = None,
        chrome_web_image: Optional[str] = None,
        large_icon: Optional[str] = None,
        url: Optional[str] = None,
        priority: Optional[int] = None,
    ) -> PushNotificationResult:
        """Asynchronously sends push notification to users by their external_id."""
        if not user_ids:
            return PushNotificationResult(success=True, recipients=0, error="Empty user list")

        string_user_ids = [str(uid) for uid in user_ids]
        extra_kwargs: Dict[str, Any] = {
            "include_aliases": {"external_id": string_user_ids},
            "target_channel": "push",
        }

        primary_img = big_picture or image_url
        if not primary_img and image_urls:
            primary_img = image_urls[0]

        if subtitle:
            extra_kwargs["subtitle"] = StringMap(en=subtitle) if ONESIGNAL_SDK_AVAILABLE else subtitle
        if badge_count is not None:
            extra_kwargs["ios_badge_type"] = "SetTo"
            extra_kwargs["ios_badge_count"] = badge_count
        if sound:
            extra_kwargs["ios_sound"] = sound
            extra_kwargs["android_sound"] = sound
        if android_channel_id or config.ONESIGNAL_DEFAULT_CHANNEL_ID:
            extra_kwargs["android_channel_id"] = android_channel_id or config.ONESIGNAL_DEFAULT_CHANNEL_ID

        if primary_img:
            extra_kwargs["big_picture"] = primary_img
            extra_kwargs["ios_attachments"] = ios_attachments or {"image": primary_img}
            extra_kwargs["chrome_web_image"] = chrome_web_image or primary_img
        elif ios_attachments:
            extra_kwargs["ios_attachments"] = ios_attachments

        if large_icon:
            extra_kwargs["large_icon"] = large_icon
        if url:
            extra_kwargs["url"] = url
        if priority is not None:
            extra_kwargs["priority"] = priority

        data_payload = dict(data) if data else {}
        if primary_img and "image_url" not in data_payload:
            data_payload["image_url"] = primary_img
            data_payload["has_image"] = True
        if image_urls and "image_urls" not in data_payload:
            data_payload["image_urls"] = image_urls
            data_payload["image_count"] = len(image_urls)

        return await cls._dispatch_and_log(
            notification_kwargs=extra_kwargs,
            target_type="USER",
            target_identifiers=string_user_ids,
            title=title,
            body=body,
            data_payload=data_payload or None,
        )

    @classmethod
    async def send_to_user(
        cls,
        user_id: Union[int, str],
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> PushNotificationResult:
        return await cls.send_to_users(
            user_ids=[user_id],
            title=title,
            body=body,
            data=data,
            **kwargs,
        )

    @classmethod
    async def send_to_subscriptions(
        cls,
        subscription_ids: List[str],
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> PushNotificationResult:
        if not subscription_ids:
            return PushNotificationResult(success=True, recipients=0, error="Empty subscription list")

        extra_kwargs: Dict[str, Any] = {
            "include_subscription_ids": subscription_ids,
        }
        extra_kwargs.update(kwargs)

        return await cls._dispatch_and_log(
            notification_kwargs=extra_kwargs,
            target_type="SUBSCRIPTION",
            target_identifiers=subscription_ids,
            title=title,
            body=body,
            data_payload=data,
        )

    @classmethod
    async def send_to_segment(
        cls,
        segment_name: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> PushNotificationResult:
        extra_kwargs: Dict[str, Any] = {
            "included_segments": [segment_name],
        }
        extra_kwargs.update(kwargs)

        return await cls._dispatch_and_log(
            notification_kwargs=extra_kwargs,
            target_type="SEGMENT",
            target_identifiers=segment_name,
            title=title,
            body=body,
            data_payload=data,
        )

    @classmethod
    async def send_to_all(
        cls,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> PushNotificationResult:
        extra_kwargs: Dict[str, Any] = {
            "included_segments": ["Subscribed Users"],
            "target_channel": "push",
        }
        extra_kwargs.update(kwargs)

        return await cls._dispatch_and_log(
            notification_kwargs=extra_kwargs,
            target_type="ALL",
            target_identifiers="ALL_SUBSCRIBED_USERS",
            title=title,
            body=body,
            data_payload=data,
        )
