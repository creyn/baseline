"""The LLM's answer for one batch, as a pydantic model (ADR-0007, point 3).

The model gives the JSON schema for structured output and parses the answer. Code in
core.py then checks every field against the words of the page.
"""
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict


class _Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class AnswerDate(_Strict):
    label: str
    text: str
    local: str
    kind: Literal['collected', 'registered', 'received', 'performed', 'released', 'printed', 'other']


class AnswerResult(_Strict):
    page: int
    name: str
    nameWords: List[str]
    value: str
    valueWords: List[str]
    unit: Optional[str]
    unitWords: List[str]
    range: Optional[str]
    rangeWords: List[str]
    rangeLow: Optional[str]
    rangeHigh: Optional[str]
    rangeKind: Literal['interval', 'lt', 'gt', 'text', 'none']
    flagPrinted: Optional[str]
    icd9: Optional[str]
    material: Optional[str]
    condition: Optional[str]
    method: Optional[str]
    analyser: Optional[str]
    dates: List[AnswerDate]
    suggestedParameter: Optional[str]


class AnswerFragment(_Strict):
    page: int
    words: List[str]


class Answer(_Strict):
    results: List[AnswerResult]
    documentDates: List[AnswerDate]
    fragments: List[AnswerFragment]


def parse(text):
    """The model's JSON text -> a plain dict for core.py. Raises pydantic.ValidationError."""
    return Answer.model_validate_json(text).model_dump()
