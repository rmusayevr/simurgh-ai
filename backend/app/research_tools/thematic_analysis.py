"""
thematic_analysis.py — Post-study qualitative analysis tool.

Implements LLM-assisted inductive coding of open-ended exit survey
responses for Chapter 5, Section 3.4.2 ("Thematic Analysis").

NOT called during experiment sessions. Invoked by researchers via:
    POST /thesis/thematic-analysis   (superuser only)

Workflow:
    1. Export exit survey free-text responses from the database.
    2. Pass them to ThematicAnalysisService.extract_themes().
    3. Use the returned theme clusters as a starting codebook.
    4. Refine manually before reporting in Chapter 5.
"""

import json
import logging
from typing import List, Dict, Any
from app.services.ai import ai_service

logger = logging.getLogger(__name__)


class ThematicAnalysisService:
    """
    Assist with thematic analysis of open-ended responses.
    Implements the semi-automated coding approach for Section 3.4.2.
    """

    async def extract_themes(self, responses: List[str]) -> Dict[str, Any]:
        """
        Use LLM to suggest initial themes from a list of open-ended text responses.
        """
        if not responses:
            return {"themes": []}

        # Format responses for the prompt
        formatted_responses = "\n".join(
            [f"- {r}" for r in responses if r and r.strip()]
        )

        prompt = f"""
You are assisting a researcher with the "Thematic Analysis" phase of a Master's Thesis on AI in Software Architecture.
Analyze the following open-ended participant responses.

DATA TO ANALYZE:
{formatted_responses}

TASK:
Identify recurring themes in these responses using 'Inductive Coding'.
Group similar concerns, praises, or observations together.

POTENTIAL THEMES (Use these if relevant, but discover new ones):
- Trust issues (lack of context, opaque reasoning)
- Quality concerns (over-engineering, security gaps)
- Positive surprises (novel insights, good risk identification)
- Usability issues (confusing terminology, information overload)

OUTPUT FORMAT (JSON ONLY):
{{
    "themes": [
        {{
        "name": "Theme Name",
        "description": "Brief definition of the theme",
        "example_quotes": ["Quote 1", "Quote 2"],
        "frequency": 5,
        "sentiment": "positive/negative/neutral"
        }}
    ]
}}
"""
        try:
            # We use a higher temperature (0.4) to allow for some interpretive flexibility
            # while keeping the JSON structure rigid.
            response_text = await ai_service._safe_api_call(
                system_prompt="You are a qualitative data analyst specializing in Thematic Analysis.",
                user_message=prompt,
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                temperature=0.3,
            )

            # Clean potential markdown formatting
            cleaned_text = (
                response_text.replace("```json", "").replace("```", "").strip()
            )
            return json.loads(cleaned_text)

        except json.JSONDecodeError:
            logger.error("Failed to parse thematic analysis JSON")
            return {
                "error": "Failed to generate structured themes",
                "raw_output": response_text,
            }
        except Exception as e:
            logger.error(f"Thematic analysis failed: {e}")
            return {"error": str(e)}
