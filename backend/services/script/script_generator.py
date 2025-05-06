import logging
from abc import ABC, abstractmethod
from typing import Optional
from google.genai import types

from core.config import settings
from core.constants import GEMINI, GROQ, PERPLEXITY

from clients.groq_client import groq_client
from clients.gemini_client import gemini_client
from clients.perplexity_client import perplexity_client

logger = logging.getLogger("vidgenai.script_generator")


class ScriptGenerator(ABC):
    @abstractmethod
    async def generate(self, celebrity_name: str) -> str:
        pass

    def _get_common_prompt(self, celebrity_name: str) -> str:
        return f"""
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


class GeminiScriptGenerator(ScriptGenerator):
    def __init__(self, model: str):
        self.client = gemini_client
        self.model = model

    async def generate(self, celebrity_name: str) -> str:
        try:
            prompt = self._get_common_prompt(celebrity_name)
            tools = [types.Tool(google_search=types.GoogleSearch())]
            logger.info(f"Generating script for {celebrity_name} using Gemini with search grounding")

            response = await self.client.aio.models.generate_content(
                model=self.model,
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
            logger.error(f"Error generating script for {celebrity_name} with Gemini: {str(e)}", exc_info=True)
            raise


class GroqScriptGenerator(ScriptGenerator):
    def __init__(self, model: str):
        self.client = groq_client
        self.model = model

    async def generate(self, celebrity_name: str) -> str:
        try:
            prompt = self._get_common_prompt(celebrity_name)
            logger.info(f"Generating script for {celebrity_name} using Groq")

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a sports historian and content creator specializing in concise, engaging scripts about sports celebrities."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )

            script = response.choices[0].message.content.strip()
            logger.info(f"Generated script for {celebrity_name} ({len(script.split())} words)")
            return script

        except Exception as e:
            logger.error(f"Error generating script for {celebrity_name} with Groq: {str(e)}", exc_info=True)
            raise


class PerplexityScriptGenerator(ScriptGenerator):
    def __init__(self, model: str):
        self.client = perplexity_client
        self.model = model

    async def generate(self, celebrity_name: str) -> str:
        prompt = self._get_common_prompt(celebrity_name)
        try:
            logger.info(f"Generating script for {celebrity_name} using Perplexity")
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a sports historian and content creator specializing in concise, engaging scripts about sports celebrities."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=500,
            )
            script = response.choices[0].message.content.strip()
            print(script)
            logger.info(f"Generated script for {celebrity_name} ({len(script.split())} words)")
            return script
        except Exception as e:
            logger.error(f"Error generating script for {celebrity_name} with Perplexity: {str(e)}", exc_info=True)
            raise



class ScriptGeneratorFactory:
    @staticmethod
    def get_generator(model_type: str) -> ScriptGenerator:
        if model_type.lower() == GEMINI:
            return GeminiScriptGenerator(model=settings.GEMINI_MODEL)
        elif model_type.lower() == GROQ:
            return GroqScriptGenerator(model=settings.GROQ_MODEL)
        elif model_type.lower() == PERPLEXITY:
            return PerplexityScriptGenerator(model=settings.PERPLEXITY_MODEL)
        else:
            raise ValueError(f"Unsupported model type: {model_type}")


class ScriptGenerationService:
    def __init__(self, primary_model: str = PERPLEXITY, fallback_model: Optional[str] = GEMINI):
        self.primary_generator = ScriptGeneratorFactory.get_generator(primary_model)
        self.fallback_generator = (
            ScriptGeneratorFactory.get_generator(fallback_model) if fallback_model else None
        )

    async def generate_script(self, celebrity_name: str) -> str:
        try:
            return await self.primary_generator.generate(celebrity_name)
        except Exception as primary_error:
            logger.error(f"Primary script generation failed for {celebrity_name}: {str(primary_error)}")
            if self.fallback_generator:
                logger.info(f"Falling back to {self.fallback_generator.__class__.__name__} for {celebrity_name}")
                try:
                    return await self.fallback_generator.generate(celebrity_name)
                except Exception as fallback_error:
                    logger.error(f"Fallback script generation failed: {str(fallback_error)}", exc_info=True)
                    raise Exception(
                        f"Failed to generate script: {str(primary_error)}. "
                        f"Fallback also failed: {str(fallback_error)}"
                    )
            else:
                raise Exception(
                    f"Failed to generate script: {str(primary_error)}. No fallback available."
                )
