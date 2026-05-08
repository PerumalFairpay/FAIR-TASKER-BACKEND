from fastapi import APIRouter, Depends, HTTPException, Body, Query
from fastapi.responses import StreamingResponse
from app.auth import get_current_user
from app.services.ai_service import chat_stream
from app.crud import ai_chat_repository as chat_repo
from app.models import AIChatSessionResponse, AIChatMessageResponse
from typing import List, Optional
import json

router = APIRouter(prefix="/ai", tags=["ai"])

@router.post("/chat")
async def chat_endpoint(
    query: str = Body(..., embed=True),
    history: list = Body(default=[], embed=True),
    session_id: Optional[str] = Body(default=None, embed=True),
    current_user: dict = Depends(get_current_user)
):
    """
    Streaming chat endpoint with history persistence.
    If session_id is provided, messages are saved to that session.
    If session_id is None, a new session is created automatically.
    """
    if not query:
        raise HTTPException(status_code=400, detail="Query is required")
        
    user_id = current_user["id"]
    
    # Auto-create session if it doesn't exist
    effective_session_id = session_id
    if not effective_session_id:
        effective_session_id = await chat_repo.create_chat_session(user_id, query)
    
    # Save user message to DB
    await chat_repo.add_chat_message(effective_session_id, "user", query)

    async def event_generator():
        full_response = ""
        # Stream output from the LangChain agent
        async for chunk in chat_stream(query, history, current_user):
            full_response += chunk
            yield chunk
        
        # Save assistant message to DB after stream finishes
        if full_response:
            await chat_repo.add_chat_message(effective_session_id, "assistant", full_response)
        
        # Send session ID in a final special chunk so frontend can update its state
        # We use a distinct format that the frontend saga can recognize
        yield f"||SESSION_ID:{effective_session_id}||"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/sessions", response_model=List[AIChatSessionResponse])
async def get_sessions(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    return await chat_repo.get_chat_sessions(current_user["id"], skip, limit)

@router.get("/sessions/{session_id}", response_model=List[AIChatMessageResponse])
async def get_session_messages(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    messages = await chat_repo.get_chat_messages(session_id, current_user["id"])
    if not messages and session_id:
        # Check if session exists but is empty, or doesn't belong to user
        sessions = await chat_repo.get_chat_sessions(current_user["id"])
        if not any(s["id"] == session_id for s in sessions):
            raise HTTPException(status_code=404, detail="Session not found")
    return messages

@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    success = await chat_repo.delete_chat_session(session_id, current_user["id"])
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Session deleted successfully"}

@router.delete("/sessions")
async def clear_history(current_user: dict = Depends(get_current_user)):
    await chat_repo.clear_all_chat_history(current_user["id"])
    return {"message": "All chat history cleared"}
