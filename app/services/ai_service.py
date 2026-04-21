import json
from datetime import datetime
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from langchain_core.prompts import ChatPromptTemplate
from typing import AsyncGenerator, List, Dict, Any
import os

from bson import ObjectId

async def get_tools_for_user(user: dict):
    """Returns an empty list as all tools have been removed."""
    return []

async def chat_stream(query: str, history: list, user: dict) -> AsyncGenerator[str, None]:
    """Generates a streaming response using LangChain's AgentExecutor, incorporating conversation history."""
    
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        
    if not api_key:
        yield "Error: GEMINI_API_KEY or GOOGLE_API_KEY environment variable is not set on the server."
        return

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash", 
        google_api_key=api_key,
        temperature=0.2,
        streaming=True
    )
    
    tools = await get_tools_for_user(user)
    
    today = datetime.now().strftime("%Y-%m-%d, %A")
    system_prompt = (
        "You are the Astro AI Assistant. Your purpose is to help users manage and query their workplace data. "
        "Maintain a helpful, formal, and objective tone throughout the conversation, utilizing relevant emojis where appropriate to enhance the interaction. "
        f"The current user is {user.get('name', 'User')} and their role is {user.get('role', 'employee')}."
        f"\nIMPORTANT: The current date and time is {today}."
    )
    
    agent = create_react_agent(llm, tools, prompt=system_prompt)

    try: 
        # Trim history to last 10 messages to keep token count low and responses fast
        MAX_HISTORY = 5
        trimmed_history = history[-MAX_HISTORY:] if len(history) > MAX_HISTORY else history

        langchain_messages = []
        for msg in trimmed_history:
            role = msg.get("role")
            content = msg.get("content")
            if role and content: 
                mapped_role = "human" if role == "user" else "assistant"
                langchain_messages.append((mapped_role, content))
                
        # Append the current query
        langchain_messages.append(("human", query))

        # LangGraph uses a different event streaming approach
        async for event in agent.astream_events(
            {"messages": langchain_messages},
            version="v2"
        ):
            kind = event["event"]
            if kind == "on_chat_model_stream":
                # We only want to yield the AI's direct responses, not the tool calling internal thoughts
                if "chunk" in event["data"]:
                    content = event["data"]["chunk"].content
                    # content can be a plain string (direct answer) OR
                    # a list of content parts (after a tool call with Gemini)
                    if isinstance(content, str) and content:
                        yield content
                    elif isinstance(content, list):
                        # Extract text from each part in the list
                        for part in content:
                            if isinstance(part, dict) and part.get("type") == "text":
                                text = part.get("text", "")
                                if text:
                                    yield text
    except Exception as e:
        yield f"\n\n[Error communicating with AI: {str(e)}]"

