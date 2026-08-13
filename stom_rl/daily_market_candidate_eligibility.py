"""Shared strict candidate-eligibility token parser."""

from __future__ import annotations


def parse_candidate_eligibility(value: object) -> bool:
    normalized = str(value).strip().casefold()
    if normalized in {"true", "1"}:
        return True
    if normalized in {"false", "0"}:
        return False
    raise ValueError("candidate eligibility token is invalid")


__all__ = ["parse_candidate_eligibility"]
