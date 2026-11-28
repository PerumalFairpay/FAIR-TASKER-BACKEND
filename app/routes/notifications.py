import logging
from datetime import datetime
from bson import ObjectId
from fastapi import APIRouter, Depends, Query, status

from app.auth import get_current_user, verify_token
from app.database import notifications_collection
from app.helper.response_helper import error_response, success_response
from app.schemas.notification import TestPushRequest
from app.services.push_notification_service import PushNotificationService

logger = logging.getLogger("notifications_route")
router = APIRouter(
    prefix="/notifications",
    tags=["notifications"],
    dependencies=[Depends(verify_token)],
)


@router.post("/test-push", summary="Send a test push notification to target user IDs")
async def send_test_push_notification(
    request: TestPushRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Test endpoint to verify OneSignal integration and delivery tracking.
    Sends push notification to target user external IDs and logs the outcome in MongoDB.
    """
    try:
        result = await PushNotificationService.send_to_users(
            user_ids=request.user_ids,
            title=request.title,
            body=request.body,
            data=request.data,
            image_url=request.image_url,
            image_urls=request.image_urls,
        )

        if not result.success:
            return error_response(
                message=f"OneSignal delivery failed: {result.error}",
                errors=result.model_dump(),
                status_code=status.HTTP_502_BAD_GATEWAY,
            )

        return success_response(
            message="Push notification dispatched successfully",
            data=result.model_dump(),
            status_code=status.HTTP_200_OK,
        )
    except Exception as e:
        logger.error(f"Unhandled error in test push route: {e}", exc_info=True)
        return error_response(
            message=f"Failed to dispatch test notification: {str(e)}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@router.get("", summary="List current user's notifications")
async def list_notifications(
    unread_only: bool = Query(False),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    user_id = str(current_user["id"])
    query = {"user_id": user_id, "is_deleted": {"$ne": True}}
    if unread_only:
        query["is_read"] = False

    skip = (page - 1) * limit
    total = await notifications_collection.count_documents(query)
    unread_count = await notifications_collection.count_documents(
        {"user_id": user_id, "is_deleted": {"$ne": True}, "is_read": False}
    )

    cursor = (
        notifications_collection.find(query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    items = [doc async for doc in cursor]

    return success_response(
        message="Notifications fetched successfully",
        data={
            "items": items,
            "unread_count": unread_count,
        },
        meta={
            "page": page,
            "limit": limit,
            "total": total,
        },
    )


@router.get("/unread-count", summary="Get unread notification count")
async def get_unread_count(current_user: dict = Depends(get_current_user)):
    user_id = str(current_user["id"])
    count = await notifications_collection.count_documents(
        {"user_id": user_id, "is_deleted": {"$ne": True}, "is_read": False}
    )
    return success_response(
        message="Unread count fetched successfully",
        data={"unread_count": count},
    )


@router.patch("/{notification_id}/read", summary="Mark a notification as read")
async def mark_notification_read(
    notification_id: str,
    current_user: dict = Depends(get_current_user),
):
    if not ObjectId.is_valid(notification_id):
        return error_response(message="Invalid notification ID", status_code=400)

    user_id = str(current_user["id"])
    now = datetime.utcnow()
    result = await notifications_collection.update_one(
        {"_id": ObjectId(notification_id), "user_id": user_id, "is_deleted": {"$ne": True}},
        {"$set": {"is_read": True, "read_at": now, "updated_at": now}},
    )
    if result.matched_count == 0:
        return error_response(message="Notification not found", status_code=404)

    return success_response(message="Notification marked as read")


@router.patch("/read-all", summary="Mark all notifications as read")
async def mark_all_notifications_read(current_user: dict = Depends(get_current_user)):
    user_id = str(current_user["id"])
    now = datetime.utcnow()
    result = await notifications_collection.update_many(
        {"user_id": user_id, "is_deleted": {"$ne": True}, "is_read": False},
        {"$set": {"is_read": True, "read_at": now, "updated_at": now}},
    )
    return success_response(
        message="All notifications marked as read",
        data={"modified_count": result.modified_count},
    )
