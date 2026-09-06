from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.responses import StreamingResponse
from app.auth import get_current_user
from app.helper.response_helper import success_response, error_response
from app.services.api import AIService

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/chat")
async def chat_endpoint(
    query: str = Body(..., embed=True),
    session_id: Optional[str] = Body(default=None, embed=True),
    current_user: dict = Depends(get_current_user)
):
    """
    Streaming chat endpoint for the AI Assistant with persistent history.
    If session_id is not provided, a new session is created.
    """
    if not query:
        raise HTTPException(status_code=400, detail="Query is required")

    user_id = str(current_user.get("id"))
    
    return StreamingResponse(
        AIService.stream_chat(
            query=query,
            user_id=user_id,
            session_id=session_id,
            current_user=current_user
        ),
        media_type="text/event-stream"
    )


@router.get("/sessions")
async def get_sessions(current_user: dict = Depends(get_current_user)):
    """Retrieve all chat sessions for the current user."""
    user_id = str(current_user.get("id"))
    sessions, err = await AIService.get_sessions(user_id)
    if err:
        return error_response(message=err, status_code=500)
    return success_response("Sessions fetched successfully", data=sessions if sessions is not None else [])


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str, current_user: dict = Depends(get_current_user)):
    """Retrieve all messages for a specific session."""
    messages, err = await AIService.get_messages(session_id)
    if err:
        return error_response(message=err, status_code=500)
    return success_response("Messages fetched successfully", data=messages if messages is not None else [])


@router.patch("/sessions/{session_id}")
async def update_session_title(
    session_id: str, 
    title: str = Body(..., embed=True),
    current_user: dict = Depends(get_current_user)
):
    """Rename a chat session."""
    session, err = await AIService.update_session_title(session_id, title)
    if err:
        status_code = 404 if "not found" in err.lower() or "invalid" in err.lower() else 500
        return error_response(message=err, status_code=status_code)
    return success_response("Session renamed successfully", data=session)


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a chat session and its history."""
    success, err = await AIService.delete_session(session_id)
    if not success:
        status_code = 404 if err and ("not found" in err.lower() or "invalid" in err.lower()) else 500
        return error_response(message=err or "Failed to delete chat session", status_code=status_code)
    return success_response("Session deleted successfully", data=[])
