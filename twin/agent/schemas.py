"""Structured output schemas for the LLM nodes.

Every LLM call in this package returns one of these. Nothing parses free text,
and — deliberately — none of these schemas has a field for a coordinate or a
risk number. The model classifies and writes prose; the grid and the scorer own
geography and arithmetic. If a future schema grows a `latitude` or a `score`,
that is the moment to stop and reconsider.
"""

from typing import List, Optional

from pydantic import BaseModel, Field

# The hazard vocabulary the host app already uses on its Report model, so an
# extracted hazard and a citizen-reported one are the same word.
HAZARD_TYPES = [
    'coastal_flooding', 'storm_surge', 'high_waves', 'swell_surge',
    'abnormal_tide', 'tsunami', 'flood', 'thunderstorm', 'heavy_rain',
    'heat_wave', 'cyclone', 'earthquake', 'wildfire', 'air_quality', 'other',
]

SEVERITY_LABELS = ['low', 'medium', 'high', 'critical']


class ExtractedHazard(BaseModel):
    """Job 1 — one alert or report, turned from prose into fields."""

    item_id: str = Field(description="The id of the source item, copied verbatim.")
    hazard_type: str = Field(
        description="One of: " + ", ".join(HAZARD_TYPES) + ". Use 'other' if unsure."
    )
    severity_label: str = Field(
        description="One of: " + ", ".join(SEVERITY_LABELS) + "."
    )
    summary: str = Field(description="One plain sentence describing the hazard.")
    area_phrase: Optional[str] = Field(
        default=None,
        description="The place named in the text, copied verbatim. Do not infer "
                    "a place that is not written there, and never output coordinates."
    )
    time_window: Optional[str] = Field(
        default=None, description="Any validity window stated in the text, verbatim."
    )


class ExtractionResult(BaseModel):
    items: List[ExtractedHazard]


class Cluster(BaseModel):
    """Job 2 — several source items that describe one real-world event."""

    cluster_id: str = Field(description="A short slug naming this event.")
    item_ids: List[str] = Field(
        description="Ids of every source item belonging to this event. "
                    "Every input id must appear in exactly one cluster."
    )
    title: str = Field(description="A short operator-facing title for the event.")
    hazard_type: str = Field(description="One of: " + ", ".join(HAZARD_TYPES) + ".")
    rationale: str = Field(
        description="One sentence on why these items are the same event."
    )


class CorrelationResult(BaseModel):
    clusters: List[Cluster]


class Brief(BaseModel):
    """Job 4 — the card an admin reads before deciding."""

    headline: str = Field(description="One line an official can act on.")
    body_md: str = Field(
        description="Three to six sentences of markdown. State what is happening, "
                    "where, on what evidence, and what is uncertain. Do not invent "
                    "numbers: use only the figures supplied in the prompt."
    )
    recommended_action: str = Field(description="One concrete next step.")
    citation_ids: List[str] = Field(
        description="Ids of the supplied sources this brief actually rests on, "
                    "including any 'sop-N' SOP passage the recommended action "
                    "draws on. Every factual claim must trace to one of them."
    )
