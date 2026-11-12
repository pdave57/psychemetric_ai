"""Pydantic schemas for question API response payloads."""

import uuid
from pydantic import BaseModel


class AnswerOptionOut(BaseModel):
    """A selectable answer option for display."""

    code:  str
    text:  str


class QuestionOut(BaseModel):
    """A question item for display during an assessment."""

    id:            uuid.UUID
    code:          str
    text:          str
    area:          str
    kind:          str
    reverse_coded: bool
    sort_order:    int
    options:       list[AnswerOptionOut]
