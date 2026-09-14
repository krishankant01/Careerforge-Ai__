import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.agents.graph import agent_graph
from app.agents.state import AgentState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["Agents"])

class AgentChatRequest(BaseModel):
    message: str
    conversation_id: uuid.UUID

class AgentChatResponse(BaseModel):
    response: str
    agents_invoked: list[str]

@router.post("/chat", response_model=AgentChatResponse)
async def agent_chat(
    request: AgentChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Endpoint for the Phase 7 LangGraph multi-agent system.
    """
    logger.info(f"Received agent chat request: {request.message}")
    
    from app.services.resume_service import list_resumes_for_user
    from app.services.job_service import list_jobs_for_user
    
    # Fetch user context
    resumes = await list_resumes_for_user(db, user_id=current_user.id)
    jobs = await list_jobs_for_user(db, user_id=current_user.id)
    
    context_parts = []
    if resumes:
        latest_resume = resumes[0]
        context_parts.append(f"--- RESUME: {latest_resume.original_filename} ---\n{latest_resume.raw_text}")
    else:
        context_parts.append("No resume provided.")
        
    if jobs:
        latest_job = jobs[0]
        context_parts.append(f"--- TARGET JOB: {latest_job.title} at {latest_job.company} ---\n{latest_job.raw_description}")
    else:
        context_parts.append("No target jobs specified.")
        
    user_context = "\n\n".join(context_parts)
    
    # Initialize the LangGraph state
    initial_state = AgentState(
        messages=[HumanMessage(content=request.message)],
        user_id=current_user.id,
        conversation_id=request.conversation_id,
        next_agent="",
        user_context=user_context,
        structured_results={}
    )
    
    # Run the graph
    try:
        # We use ainvoke to run the async graph
        # Recursion limit prevents infinite loops between agents
        final_state = await agent_graph.ainvoke(initial_state, {"recursion_limit": 10})
    except Exception as e:
        logger.error(f"Error during graph execution: {e}")
        raise HTTPException(status_code=500, detail="Internal agent execution error.")
        
    # Extract the messages from the final state
    messages = final_state.get("messages", [])
    
    # Get the last AI message
    response_text = "I'm sorry, I couldn't process your request."
    agents_invoked = []
    
    # Trace the execution
    for msg in messages:
        if isinstance(msg, AIMessage):
            # If it has a name, it's an agent response
            if msg.name:
                agents_invoked.append(msg.name)
            response_text = msg.content
            
    # Remove duplicates from invoked list
    agents_invoked = list(dict.fromkeys(agents_invoked))
    
    return AgentChatResponse(
        response=response_text,
        agents_invoked=agents_invoked
    )
