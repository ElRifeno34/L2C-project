"""Annex A records. Unknown reinforcement attributes remain null."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Armature(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    repere: str | None = None
    diametre: str | None = None
    quantite: int | None = Field(default=None, ge=0)
    espacement_mm: float | None = Field(default=None, gt=0)
    longueur_mm: float | None = Field(default=None, gt=0)


class Annotation(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    id: str
    source: Literal["plan", "atelier"]
    fichier: str
    feuillet: str
    page: int = Field(ge=1)
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    type_element: str
    element: str
    armature: list[Armature] = Field(min_length=1)

    @field_validator('id', 'fichier', 'feuillet', 'type_element', 'element')
    @classmethod
    def identified_reference(cls, value):
        if not value.strip():
            raise ValueError('Identified records require non-empty references.')
        return value
