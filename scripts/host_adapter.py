"""Minimal local host adapter; no model SDK, network or vendor hook format.
The host binds identities, classifies provenance, and calls before_reply on every
turn. A host-supplied classification can be wrong; this adapter does not infer it.
"""
from __future__ import annotations
from datetime import datetime
from typing import Any
from memory_core import Context, Memory

class LocalPreferenceHost:
    def __init__(self, memory: Memory, context: Context):
        self.memory = memory
        self.context = context

    def before_reply(self, scopes: list[str], session_id: str,
                     now: datetime | None = None, *, concept_ids: list[str] | None = None) -> dict[str, Any]:
        return self.memory.compile(self.context, scopes, session_id=session_id, now=now, concept_ids=concept_ids)

    def commit_user_signal(self, signal: dict[str, Any], *, now: datetime | None = None,
                           expected_revision: int | None = None) -> dict[str, Any]:
        return self.memory.observe(self.context, signal, now=now, expected_revision=expected_revision)
