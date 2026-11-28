from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class PushNotificationPayload(BaseModel):
    title: str = Field(..., description="Notification heading/title")
    body: str = Field(..., description="Notification body content")
    subtitle: Optional[str] = Field(default=None, description="Optional iOS subtitle")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Custom dictionary payload for deep-linking")
    sound: Optional[str] = Field(default=None, description="Custom sound filename or default")
    badge_count: Optional[int] = Field(default=None, description="iOS badge count number")
    android_channel_id: Optional[str] = Field(default=None, description="Android notification channel ID")
    big_picture: Optional[str] = Field(default=None, description="Large banner image URL for Android & Web")
    image_url: Optional[str] = Field(default=None, description="Primary image URL (alias for big_picture / ios_attachments)")
    image_urls: Optional[List[str]] = Field(default=None, description="List of all image attachment URLs for multi-image payloads")
    ios_attachments: Optional[Dict[str, str]] = Field(default=None, description="iOS media attachments mapping")
    chrome_web_image: Optional[str] = Field(default=None, description="Chrome web push image banner URL")
    large_icon: Optional[str] = Field(default=None, description="Small icon / avatar thumbnail URL")
    url: Optional[str] = Field(default=None, description="URL or deep-link to open on tap")
    priority: Optional[int] = Field(default=None, description="Delivery priority (e.g. 10 for high)")


class PushNotificationResult(BaseModel):
    success: bool
    notification_id: Optional[str] = None
    recipients: int = 0
    error: Optional[str] = None
    log_id: Optional[str] = None


class TestPushRequest(BaseModel):
    user_ids: List[Union[int, str]] = Field(..., description="List of user IDs (external IDs) to target")
    title: str = Field(default="Test Notification", description="Push notification title")
    body: str = Field(default="This is a test notification from FairPay HRM Backend.", description="Push notification body")
    image_url: Optional[str] = Field(default=None, description="Optional banner image URL")
    image_urls: Optional[List[str]] = Field(default=None, description="Optional list of multiple image URLs")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Optional custom key-value payload")
