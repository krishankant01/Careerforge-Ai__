import asyncio
import uuid
from langchain_core.messages import HumanMessage
from app.agents.state import AgentState
from app.agents.graph import agent_graph

async def main():
    state = AgentState(
        messages=[HumanMessage(content="Hello! Can you help me improve my resume?")],
        user_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        next_agent="",
        structured_results={}
    )
    result = await agent_graph.ainvoke(state, {"recursion_limit": 5})
    print("MESSAGES:")
    for msg in result["messages"]:
        print(msg.content)
        
if __name__ == "__main__":
    asyncio.run(main())
