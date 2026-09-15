import logging
from langchain_core.messages import AIMessage
from app.services.ai import get_ai_provider
from app.agents.state import AgentState

logger = logging.getLogger(__name__)

async def _call_agent(state: AgentState, role_description: str, agent_name: str) -> dict:
    """Helper function to execute an agent node."""
    logger.info(f"--- {agent_name.upper()} ---")
    provider = get_ai_provider()
    
    if not provider:
        error_msg = f"{agent_name} failed: No AI provider configured."
        logger.error(error_msg)
        return {"messages": [AIMessage(content=error_msg, name=agent_name)]}

    # Extract conversation history
    history = state.get("messages", [])
    history_str = ""
    for msg in history:
        prefix = "User" if msg.type == "human" else "Assistant"
        history_str += f"{prefix}: {msg.content}\n"

    system_prompt = (
        f"You are the {agent_name} in a career and coding multi-agent system.\n"
        f"Your role: {role_description}\n\n"
        "Instructions:\n"
        "1. Provide a helpful, concise, and structured response based on the conversation history.\n"
        "2. If you need more information to perform your task, ask the user for it.\n"
        "3. Focus ONLY on your specific domain. Do not try to perform tasks meant for other agents."
    )
    
    # Use the last message as the primary query, but provide history for context
    last_message = history[-1].content if history else ""
    user_prompt = f"Conversation History:\n{history_str}\n\nUser Request: {last_message}"

    try:
        response_text = await provider.generate_text(system_prompt, user_prompt, max_tokens=1500)
    except Exception as e:
        logger.error(f"{agent_name} generation failed: {e}")
        response_text = f"I'm sorry, I encountered an error while processing your request as {agent_name}."

    return {
        "messages": [AIMessage(content=response_text, name=agent_name)]
    }

async def resume_node(state: AgentState) -> dict:
    return await _call_agent(
        state, 
        "Analyze resumes, extract skills, suggest formatting improvements, and provide feedback on structure.",
        "ResumeAgent"
    )

async def job_node(state: AgentState) -> dict:
    return await _call_agent(
        state,
        "Analyze job descriptions, extract key requirements, identify preferred skills, and explain the role's responsibilities.",
        "JobAgent"
    )

async def skill_gap_node(state: AgentState) -> dict:
    return await _call_agent(
        state,
        "Compare a user's resume or stated skills against a job description. Identify missing skills and provide actionable advice to bridge the gap.",
        "SkillGapAgent"
    )

async def github_node(state: AgentState) -> dict:
    # In a full implementation, this agent would have tool access to the rag_service or github_service
    # to query the database. For now, it provides guidance based on context.
    return await _call_agent(
        state,
        "Answer questions about the user's tracked GitHub repositories, codebase structure, and project architecture.",
        "GitHubAgent"
    )

async def code_review_node(state: AgentState) -> dict:
    return await _call_agent(
        state,
        "Analyze provided code snippets for bugs, security vulnerabilities, performance bottlenecks, and style issues. Provide constructive feedback and suggested fixes.",
        "CodeReviewAgent"
    )

async def test_generation_node(state: AgentState) -> dict:
    return await _call_agent(
        state,
        "Write robust unit tests for provided code snippets. Consider edge cases, boundary conditions, and proper assertions.",
        "TestGenerationAgent"
    )

async def research_node(state: AgentState) -> dict:
    return await _call_agent(
        state,
        "Research career paths, industry trends, salary data, or general technical concepts. Provide factual and objective summaries.",
        "ResearchAgent"
    )

async def project_recommendation_node(state: AgentState) -> dict:
    logger.info("--- PROJECT RECOMMENDATION AGENT ---")
    provider = get_ai_provider()
    if not provider:
        return {"messages": [AIMessage(content="ProjectRecommendationAgent failed: No AI provider configured.", name="ProjectRecommendationAgent")]}
        
    user_context = state.get("user_context", "")
    
    system_prompt = (
        "You are the ProjectRecommendationAgent. Your task is to suggest realistic and impactful portfolio "
        "projects to help the user build missing skills and improve their resume, tailored to their target job.\n\n"
        "You MUST output exactly a JSON object with a single key 'projects', which is an array of objects. "
        "Each project object MUST have the following keys:\n"
        "- problem_statement (string)\n"
        "- features (array of strings)\n"
        "- tech_stack (array of strings)\n"
        "- architecture (string)\n"
        "- database_requirements (string)\n"
        "- APIs (string)\n"
        "- milestones (array of strings)\n"
        "- testing_strategy (string)\n"
        "- deployment_strategy (string)\n"
        "- skills_gained (array of strings)\n"
    )
    
    user_prompt = f"User Context (Resume & Jobs):\n{user_context}\n\nPlease recommend 2 impactful portfolio projects. Output JSON only."
    
    try:
        data = await provider.generate_json(system_prompt, user_prompt, max_tokens=2500)
        projects = data.get("projects", [])
        
        # Format the JSON into markdown
        markdown_parts = ["Here are some personalized project recommendations to boost your portfolio:\n"]
        for idx, proj in enumerate(projects, 1):
            markdown_parts.append(f"### Project {idx}: {proj.get('problem_statement', 'Untitled Project')}")
            markdown_parts.append(f"**Architecture:** {proj.get('architecture', 'N/A')}")
            markdown_parts.append(f"**Tech Stack:** {', '.join(proj.get('tech_stack', []))}")
            markdown_parts.append(f"**Database:** {proj.get('database_requirements', 'N/A')}")
            markdown_parts.append(f"**APIs:** {proj.get('APIs', 'N/A')}")
            
            markdown_parts.append("**Features:**")
            for f in proj.get('features', []): markdown_parts.append(f"- {f}")
                
            markdown_parts.append("**Milestones:**")
            for m in proj.get('milestones', []): markdown_parts.append(f"- {m}")
                
            markdown_parts.append(f"**Testing Strategy:** {proj.get('testing_strategy', 'N/A')}")
            markdown_parts.append(f"**Deployment:** {proj.get('deployment_strategy', 'N/A')}")
            
            markdown_parts.append("**Skills Gained:**")
            for s in proj.get('skills_gained', []): markdown_parts.append(f"- {s}")
            markdown_parts.append("\n---\n")
            
        response_text = "\n".join(markdown_parts)
    except Exception as e:
        logger.error(f"ProjectRecommendationAgent generation failed: {e}")
        response_text = "I encountered an error generating your projects. Please try again."

    return {"messages": [AIMessage(content=response_text, name="ProjectRecommendationAgent")]}

async def roadmap_node(state: AgentState) -> dict:
    logger.info("--- ROADMAP AGENT ---")
    provider = get_ai_provider()
    if not provider:
        return {"messages": [AIMessage(content="RoadmapAgent failed: No AI provider configured.", name="RoadmapAgent")]}
        
    user_context = state.get("user_context", "")
    
    system_prompt = (
        "You are the RoadmapAgent. Your task is to generate a personalized 30/60/90-day learning roadmap "
        "based on the user's skill gaps and target job.\n\n"
        "You MUST output exactly a JSON object with the following structure:\n"
        "{\n"
        "  'days_30': {'focus': 'string', 'milestones': ['string'], 'resources': ['string']},\n"
        "  'days_60': {'focus': 'string', 'milestones': ['string'], 'resources': ['string']},\n"
        "  'days_90': {'focus': 'string', 'milestones': ['string'], 'resources': ['string']}\n"
        "}\n"
    )
    
    user_prompt = f"User Context (Resume & Jobs):\n{user_context}\n\nPlease generate the 30/60/90 day roadmap. Output JSON only."
    
    try:
        data = await provider.generate_json(system_prompt, user_prompt, max_tokens=2000)
        
        markdown_parts = ["Here is your personalized 30/60/90-day learning roadmap:\n"]
        
        for period in ["days_30", "days_60", "days_90"]:
            period_data = data.get(period, {})
            title = period.replace("_", " ").title()
            markdown_parts.append(f"### {title}: {period_data.get('focus', 'General Learning')}")
            
            markdown_parts.append("**Milestones:**")
            for m in period_data.get('milestones', []): markdown_parts.append(f"- {m}")
                
            markdown_parts.append("**Resources:**")
            for r in period_data.get('resources', []): markdown_parts.append(f"- {r}")
            markdown_parts.append("\n")
            
        response_text = "\n".join(markdown_parts)
    except Exception as e:
        logger.error(f"RoadmapAgent generation failed: {e}")
        response_text = "I encountered an error generating your learning roadmap. Please try again."

    return {"messages": [AIMessage(content=response_text, name="RoadmapAgent")]}

async def interview_node(state: AgentState) -> dict:
    logger.info("--- INTERVIEW AGENT ---")
    provider = get_ai_provider()
    if not provider:
        return {"messages": [AIMessage(content="InterviewAgent failed: No AI provider configured.", name="InterviewAgent")]}
        
    user_context = state.get("user_context", "")
    history = state.get("messages", [])
    
    # Check if the previous message was from the InterviewAgent
    is_answering = False
    if len(history) >= 2:
        prev_msg = history[-2]
        if isinstance(prev_msg, AIMessage) and prev_msg.name == "InterviewAgent":
            is_answering = True

    if is_answering:
        system_prompt = (
            "You are the InterviewAgent conducting a mock interview. The user has just answered your previous question.\n\n"
            "Your task is to:\n"
            "1. Evaluate their answer based on their specific career context.\n"
            "2. Provide constructive feedback (what was good, what could be improved).\n"
            "3. Ask the NEXT relevant interview question.\n\n"
            "You MUST output exactly a JSON object with the following structure:\n"
            "{\n"
            "  'evaluation': 'string',\n"
            "  'feedback': 'string',\n"
            "  'next_question': 'string'\n"
            "}\n"
        )
    else:
        system_prompt = (
            "You are the InterviewAgent starting a new mock interview. Based on the user's resume, job targets, and context, "
            "generate the FIRST personalized interview question.\n\n"
            "You MUST output exactly a JSON object with the following structure:\n"
            "{\n"
            "  'next_question': 'string'\n"
            "}\n"
        )

    # Extract conversation history for context
    history_str = ""
    # Only send the last few turns so the model doesn't get confused
    for msg in history[-4:]:
        prefix = "User" if msg.type == "human" else "Assistant"
        history_str += f"{prefix}: {msg.content}\n"

    user_prompt = f"User Context:\n{user_context}\n\nRecent Conversation:\n{history_str}\n\nPlease generate the next step. Output JSON only."
    
    try:
        data = await provider.generate_json(system_prompt, user_prompt, max_tokens=1500)
        
        markdown_parts = []
        if is_answering:
            if "evaluation" in data:
                markdown_parts.append(f"**Evaluation:** {data['evaluation']}")
            if "feedback" in data:
                markdown_parts.append(f"**Feedback:** {data['feedback']}")
            markdown_parts.append("\n---\n")
            
        if "next_question" in data:
            markdown_parts.append(f"**Next Question:**\n{data['next_question']}")
        else:
            markdown_parts.append("That concludes our mock interview. Great job!")
            
        response_text = "\n\n".join(markdown_parts)
    except Exception as e:
        logger.error(f"InterviewAgent generation failed: {e}")
        response_text = "I encountered an error processing the interview. Let's try that again."

    return {"messages": [AIMessage(content=response_text, name="InterviewAgent")]}
