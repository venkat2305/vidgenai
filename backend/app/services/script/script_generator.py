import logging
from groq import AsyncGroq
from app.core.config import settings

logger = logging.getLogger("vidgenai.script_generator")


async def generate_script(celebrity_name: str) -> str:
    """
    Generate a script about a sports celebrity using Groq API.
    
    Args:
        celebrity_name: Name of the sports celebrity
    Returns:
        Generated script text
    """
    try:
        client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        
        prompt = f"""
        Create an engaging, factual 45-second script about the sports career and achievements of {celebrity_name}.
        
        The script should:
        1. Start with an attention-grabbing fact or achievement
        2. Cover key milestones in their career
        3. Mention statistics or records they've set
        4. Include a memorable quote or anecdote if relevant
        5. End with their legacy or impact on their sport
        
        Keep the script concise (around 120-150 words) and focused on the most interesting aspects of their career.
        The tone should be informative yet conversational, suitable for a short-form video.
        
        Only return the script text, with no additional formatting or commentary.
        """
        
        response = await client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": "You are a sports historian and content creator specializing in concise, engaging scripts about sports celebrities."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )
        
        script = response.choices[0].message.content.strip()
        logger.info(f"Generated script for {celebrity_name} ({len(script.split())} words)")
        return script
        
    except Exception as e:
        logger.error(f"Error generating script for {celebrity_name}: {str(e)}", exc_info=True)
        raise Exception(f"Failed to generate script: {str(e)}")
