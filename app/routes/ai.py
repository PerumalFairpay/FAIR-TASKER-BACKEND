from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.responses import StreamingResponse
from app.auth import get_current_user
from app.services.ai_service import chat_stream
from app.crud.repository import repository as repo
from typing import Optional
import json

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
    
    # 1. Handle Session Creation
    active_session_id = session_id
    is_new_session = False
    if not active_session_id:
        # Auto-create session with first 30 chars of query as title
        title = (query[:30] + '...') if len(query) > 30 else query
        session = await repo.create_chat_session(user_id, title)
        active_session_id = session["id"]
        is_new_session = True

    # 2. Fetch existing history for this session
    db_messages = await repo.get_chat_messages(active_session_id)
    history = [{"role": msg["role"], "content": msg["content"]} for msg in db_messages]

    # 3. Save User Message to DB
    await repo.create_chat_message(active_session_id, "user", query)

    async def event_generator():
        full_response = ""
        
        # If it's a new session, yield the session ID first so the frontend can update its state
        if is_new_session:
            yield f"__SESSION_ID__:{active_session_id}\n"

        # Stream output from the LangChain agent
        async for chunk in chat_stream(query, history, current_user):
            full_response += chunk
            yield chunk
        
        # 4. Save Assistant Response to DB after streaming finishes
        if full_response.strip():
            await repo.create_chat_message(active_session_id, "assistant", full_response)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/sessions")
async def get_sessions(current_user: dict = Depends(get_current_user)):
    """Retrieve all chat sessions for the current user."""
    user_id = str(current_user.get("id"))
    return await repo.get_chat_sessions(user_id)

@router.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str, current_user: dict = Depends(get_current_user)):
    """Retrieve all messages for a specific session."""
    # Note: In a production app, verify session_id belongs to current_user
    return await repo.get_chat_messages(session_id)

@router.patch("/sessions/{session_id}")
async def update_session_title(
    session_id: str, 
    title: str = Body(..., embed=True),
    current_user: dict = Depends(get_current_user)
):
    """Rename a chat session."""
    return await repo.update_chat_session_title(session_id, title)

@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a chat session and its history."""
    success = await repo.delete_chat_session(session_id)
    return {"success": success}
