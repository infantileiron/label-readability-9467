from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from src.constants.enums import Decision, Order

Code = Annotated[str, StringConstraints(min_length=2, max_length=30, pattern=r'^[A-Z0-9][A-Z0-9-]+$')]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=60)]


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Credentials(Input):
    username: Annotated[str, StringConstraints(min_length=1, max_length=40)]
    password: Annotated[str, StringConstraints(min_length=1, max_length=128)]


class VersionInput(Input):
    code: Code
    title: Title
    exhibit: Title
    body: Annotated[str, StringConstraints(strip_whitespace=True, min_length=8, max_length=500)]
    type_pt: int = Field(ge=10, le=72)
    line_height: float = Field(ge=1, le=3, multiple_of=0.01)


class StudyInput(Input):
    code: Code
    title: Title
    station: Title
    reading_task: Annotated[str, StringConstraints(strip_whitespace=True, min_length=4, max_length=240)]
    old_id: int = Field(gt=0)
    new_id: int = Field(gt=0)

    @model_validator(mode='after')
    def different_versions(self):
        if self.old_id == self.new_id:
            raise ValueError('旧版与样张须使用两个版本')
        return self


class PairInput(Input):
    reading_order: Order
    old_ok: bool | None = Field(strict=True)
    new_ok: bool | None = Field(strict=True)


class RunInput(Input):
    confidence: Literal[90, 95, 99]


class ReviewInput(Input):
    decision: Decision
    note: Annotated[str, StringConstraints(strip_whitespace=True, min_length=6, max_length=500)]
