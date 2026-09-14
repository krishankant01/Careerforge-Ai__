import uuid
from typing import Annotated, TypedDict, Any
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    """
    The shared state passed between all agents in the LangGraph multi-agent system.
    """
    # The conversation history
    messages: Annotated[list[BaseMessage], add_messages]
    
    # The current user's ID
    user_id: uuid.UUID
    
    # The current conversation ID
    conversation_id: uuid.UUID
    
    # Routing flag used by the supervisor to determine the next node
    next_agent: str
    
    # Text summary of the user's career profile (resume, jobs, etc.) to ground the agents
    user_context: str
    
    # A generic dictionary to hold structured data produced by specialized agents
    structured_results: dict[str, Any]
