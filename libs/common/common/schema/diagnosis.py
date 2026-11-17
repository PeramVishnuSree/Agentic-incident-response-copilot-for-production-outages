"""Diagnosis output models produced by correlation + RCA (E5, E6, NF3)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class EvidenceType(StrEnum):
    METRIC = "metric"
    LOG = "log"
    K8S_EVENT = "k8s_event"
    DEPLOYMENT = "deployment"
    ALERT = "alert"


class Evidence(BaseModel):
    id: str
    type: EvidenceType
    raw_ref: str = Field(..., description="Must resolve in the incident store (E6/NF3).")
    summary: str = ""


class Candidate(BaseModel):
    service: str
    score: float
    rank: int
    evidence: list[str] = Field(default_factory=list, description="Evidence ids")
    confidence: float = 0.0
    uncertainty: str = ""


class Incident(BaseModel):
    id: str
    started_at: datetime
    services: list[str]
    signal_refs: list[str] = Field(default_factory=list)
    candidates: list[Candidate] = Field(default_factory=list)
