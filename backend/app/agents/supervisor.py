import logging
from typing import Literal
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from app.services.ai import get_ai_provider
from app.agents.state import AgentState

logger = logging.getLogger(__name__)

# Define the members of the multi-agent system
members = [
    "ResumeAgent",
    "JobAgent",
    "SkillGapAgent",
    "GitHubAgent",
    "CodeReviewAgent",
    "TestGenerationAgent",
    "ResearchAgent",
    "ProjectRecommendationAgent",
    "InterviewAgent",
    "RoadmapAgent"
]

options = ["FINISH"] + members

def create_supervisor_chain():
    system_prompt = (
        "You are the Supervisor of a career and coding multi-agent system. "
        "Your role is to analyze the user's request and the conversation history, "
        "then route the request to the most appropriate specialized agent.\n\n"
        "Here are the available agents and their responsibilities:\n"
        "- ResumeAgent: Analyzes resumes, extracts skills, reviews structure.\n"
        "- JobAgent: Analyzes job descriptions, extracts requirements.\n"
        "- SkillGapAgent: Compares resumes to jobs and identifies missing skills.\n"
        "- GitHubAgent: Answers questions about the user's tracked GitHub repositories.\n"
        "- CodeReviewAgent: Analyzes provided code snippets for bugs, security, or style issues.\n"
        "- TestGenerationAgent: Writes unit tests for provided code snippets.\n"
        "- ResearchAgent: Researches career paths, salaries, or general technical concepts.\n"
        "- ProjectRecommendationAgent: Suggests portfolio projects to build missing skills.\n"
        "- InterviewAgent: Conducts mock interviews or provides interview preparation advice.\n"
        "- RoadmapAgent: Generates a personalized 30/60/90-day learning roadmap.\n\n"
        "If a specific agent is needed to answer the user's latest request, output that agent's name.\n"
        "If the user's request is a general greeting, an acknowledgment, or if the conversation is complete, output 'FINISH'."
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="messages"),
        (
            "system",
            "Given the conversation above, who should act next? "
            "Or should we FINISH? Select one of: {options}"
        )
    ])

    return prompt

async def supervisor_node(state: AgentState) -> dict:
    """
    The Supervisor node logic. Uses the configured LLM to determine the next agent.
    """
    logger.info("--- SUPERVISOR NODE ---")
    provider = get_ai_provider()
    
    if not provider:
        logger.error("No AI provider configured for Supervisor.")
        return {"next_agent": "FINISH"}

    # We need to use the Langchain interface if possible, or build the prompt manually.
    # Since we want structured output, let's use the provider's generate_json method
    # and map it to our options.
    
    # Extract recent messages to provide context
    recent_messages = state.get("messages", [])[-5:]
    history_str = ""
    for msg in recent_messages:
        prefix = "User" if msg.type == "human" else "Assistant"
        history_str += f"{prefix}: {msg.content}\n"

    system_prompt = (
        "You are the Supervisor of a career and coding multi-agent system. "
        "Your role is to analyze the user's request and the conversation history, "
        "then route the request to the most appropriate specialized agent.\n\n"
        "Here are the available agents:\n"
        "- ResumeAgent: Analyzes resumes, extracts skills, reviews structure.\n"
        "- JobAgent: Analyzes job descriptions, extracts requirements.\n"
        "- SkillGapAgent: Compares resumes to jobs and identifies missing skills.\n"
        "- GitHubAgent: Answers questions about the user's tracked GitHub repositories.\n"
        "- CodeReviewAgent: Analyzes provided code snippets for bugs, security, or style issues.\n"
        "- TestGenerationAgent: Writes unit tests for provided code snippets.\n"
        "- ResearchAgent: Researches career paths, salaries, or general technical concepts.\n"
        "- ProjectRecommendationAgent: Suggests portfolio projects to build missing skills.\n"
        "- InterviewAgent: Conducts mock interviews or provides interview preparation advice.\n"
        "- RoadmapAgent: Generates a personalized 30/60/90-day learning roadmap.\n\n"
        "Rules:\n"
        "1. Output ONLY a JSON object with a single key 'next_agent'.\n"
        f"2. The value must be exactly one of: {options}\n"
        "3. If the user's request is a greeting, acknowledgment, or if the task is complete, choose 'FINISH'."
    )
    
    user_prompt = f"Conversation History:\n{history_str}\n\nBased on the history, who should act next? Output JSON only."
    
    try:
        data = await provider.generate_json(system_prompt, user_prompt, max_tokens=100)
        next_agent = data.get("next_agent")
        
        if next_agent not in options:
            logger.warning(f"Supervisor returned invalid agent: {next_agent}. Defaulting to FINISH.")
            next_agent = "FINISH"
            
    except Exception as e:
        logger.error(f"Supervisor failed to determine next agent: {e}")
        next_agent = "FINISH"

    logger.info(f"Supervisor decision: {next_agent}")
    return {"next_agent": next_agent}
