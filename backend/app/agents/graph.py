from langgraph.graph import StateGraph, END
from app.agents.state import AgentState
from app.agents.supervisor import supervisor_node, members
from app.agents.worker_agents import (
    resume_node,
    job_node,
    skill_gap_node,
    github_node,
    code_review_node,
    test_generation_node,
    research_node,
    project_recommendation_node,
    interview_node,
    roadmap_node
)

def build_graph():
    """
    Constructs the LangGraph multi-agent orchestration workflow.
    """
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("Supervisor", supervisor_node)
    workflow.add_node("ResumeAgent", resume_node)
    workflow.add_node("JobAgent", job_node)
    workflow.add_node("SkillGapAgent", skill_gap_node)
    workflow.add_node("GitHubAgent", github_node)
    workflow.add_node("CodeReviewAgent", code_review_node)
    workflow.add_node("TestGenerationAgent", test_generation_node)
    workflow.add_node("ResearchAgent", research_node)
    workflow.add_node("ProjectRecommendationAgent", project_recommendation_node)
    workflow.add_node("InterviewAgent", interview_node)
    workflow.add_node("RoadmapAgent", roadmap_node)
    
    # All worker agents report back to END to prevent infinite loops and save LLM calls
    for member in members:
        workflow.add_edge(member, END)
        
    # The supervisor is the entry point
    workflow.set_entry_point("Supervisor")
    
    # Conditional routing from the supervisor to the appropriate worker agent or FINISH
    conditional_map = {k: k for k in members}
    conditional_map["FINISH"] = END
    
    workflow.add_conditional_edges("Supervisor", lambda x: x["next_agent"], conditional_map)
    
    return workflow.compile()

# A compiled instance of the graph ready to use
agent_graph = build_graph()
