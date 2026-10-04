"""Annex A records. Unknown reinforcement attributes remain null."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class Armature(BaseModel):
    model_config = ConfigDict(extra="forbid")
    repere: str | None = None
    diametre: str | None = None
    quantite: int | None = Field(default=None, ge=0)
    espacement_mm: float | None = Field(default=None, gt=0)
    longueur_mm: float | None = Field(default=None, gt=0)


class Annotation(BaseModel):
    model_config = ConfigDict(extra="forbid")
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
