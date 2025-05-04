import logging
import os
from google import genai
from google.genai import types
from app.core.config import settings

logger = logging.getLogger("vidgenai.script_generator")


async def generate_script(celebrity_name: str) -> str:
    try:
        _gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)

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

        tools = [types.Tool(google_search=types.GoogleSearch())]

        logger.info(f"Generating script for {celebrity_name} using Gemini with search grounding")

        response = await _gemini_client.aio.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=tools,
                temperature=0.2,
                response_mime_type="text/plain",
            ),
        )

        script = response.text.strip()
        logger.info(f"Generated script for {celebrity_name} ({len(script.split())} words)")
        return script

    except Exception as e:
        logger.error(f"Error generating script for {celebrity_name}: {str(e)}", exc_info=True)

        # Fall back to using Groq if Gemini fails
        try:
            logger.info(f"Falling back to Groq for script generation for {celebrity_name}")
            from groq import AsyncGroq

            client = AsyncGroq(api_key=settings.GROQ_API_KEY)

            fallback_prompt = f"""
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
                    {"role": "user", "content": fallback_prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )

            fallback_script = response.choices[0].message.content.strip()
            logger.info(f"Generated fallback script for {celebrity_name} using Groq ({len(fallback_script.split())} words)")
            return fallback_script

        except Exception as fallback_error:
            logger.error(f"Fallback script generation failed: {str(fallback_error)}", exc_info=True)
            raise Exception(f"Failed to generate script: {str(e)}. Fallback also failed: {str(fallback_error)}")
