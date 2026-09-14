import uuid
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_agent_chat_endpoint(client: AsyncClient, auth_headers: dict, monkeypatch):
    """
    Test the LangGraph multi-agent chat endpoint.
    Mocks the agent graph execution so it doesn't try to call an LLM.
    """
    from langchain_core.messages import AIMessage
    
    # Mock the ainvoke method of the agent graph
    async def mock_ainvoke(state, config):
        return {
            "messages": [
                AIMessage(content="Hello from the Supervisor", name="Supervisor"),
                AIMessage(content="Here is your resume feedback", name="ResumeAgent")
            ]
        }
        
    monkeypatch.setattr("app.api.agent_api.agent_graph.ainvoke", mock_ainvoke)
    
    # Send request
    conv_id = uuid.uuid4()
    response = await client.post(
        "/api/agents/chat",
        json={
            "message": "Review my resume",
            "conversation_id": str(conv_id)
        },
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["response"] == "Here is your resume feedback"
    assert "Supervisor" in data["agents_invoked"]
    assert "ResumeAgent" in data["agents_invoked"]
