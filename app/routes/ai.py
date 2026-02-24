from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.responses import StreamingResponse
from app.auth import get_current_user
from app.services.ai_service import chat_stream
import json

router = APIRouter(prefix="/ai", tags=["ai"])

@router.post("/chat")
async def chat_endpoint(
    query: str = Body(..., embed=True),
    current_user: dict = Depends(get_current_user)
):
    """
    Streaming chat endpoint for the AI Assistant.
    Expects JSON body: {"query": "Your question"}
    """
    if not query:
        raise HTTPException(status_code=400, detail="Query is required")
        
    async def event_generator():
        # Stream output from the LangChain agent
        async for chunk in chat_stream(query, current_user):
            # Format as Server-Sent Events (SSE) if strictly required, 
            # but simpler text streaming works for many frontend implementations too.
            # We'll use simple text stream for ease of ReadableStream parsing.
            yield chunk

    return StreamingResponse(event_generator(), media_type="text/event-stream")
