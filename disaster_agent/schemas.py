"""Structured output for the narrative step.

Same rule as twin/agent/schemas.py: this schema has no field for a coordinate,
a risk number or a time. Every one of those is already decided by
`advect.py`'s arithmetic before the model ever sees the hotspot; the LLM's
only job is to turn the numbers it is handed into a paragraph a human can act
on, and to cite which of the supplied contributing sources it actually used.
"""

from typing import List

from pydantic import BaseModel, Field


class PredictionBrief(BaseModel):
    headline: str = Field(
        description="One line an analyst can act on: what, roughly where, "
                    "roughly when. No numbers beyond what was supplied."
    )
    narrative: str = Field(
        description="Two to four sentences: what the wind, cloud and heat "
                    "signal supplied in the prompt indicates, and why the "
                    "named region is the one projected to be affected. Use "
                    "only the figures given - do not invent a percentage, "
                    "distance or timestamp that was not in the prompt."
    )
    recommended_action: str = Field(
        description="One concrete next step for a disaster-management analyst."
    )
    confidence_label: str = Field(
        description="One of: low, medium, high - the analyst's read on how "
                    "solid this projection is given how many sources agree "
                    "and how well-aligned they are."
    )
    citation_sources: List[str] = Field(
        description="Names of the contributing source regions this brief "
                    "actually rests on, copied verbatim from the prompt."
    )
