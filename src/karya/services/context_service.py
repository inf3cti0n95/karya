"""Context service for generating agent workspace context."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, List

from karya.core.filesystem import normalize_root, CONTEXT_DIR
from karya.services.ticket_service import TicketService
from karya.services.epic_service import EpicService
from karya.services.adr_service import ADRService
from karya.core.models import ADRStatus

class ContextService:
    def __init__(self, root: Path):
        self.root = normalize_root(root)
        self._tickets = TicketService(self.root)
        self._epics = EpicService(self.root)
        self._adrs = ADRService(self.root)

    def _estimate_tokens(self, text: str) -> int:
        return len(text) // 4

    def build_context(self, ticket_id: str, budget: int = 4000) -> Dict[str, Any]:
        ticket = self._tickets.get(ticket_id)
        
        sections = []
        excluded = []
        total_tokens = 0
        
        # 1. The Ticket itself (Always)
        ticket_data = ticket.model_dump(mode="json")
        ticket_text = f"TICKET {ticket.id}\\nGoal: {ticket.goal_text}"
        ticket_tokens = self._estimate_tokens(ticket_text)
        sections.append({
            "type": "ticket",
            "id": ticket.id,
            "score": 1.00,
            "tokens": ticket_tokens,
            "content": ticket_data
        })
        total_tokens += ticket_tokens
        
        # 2. Blockers (Always if they exist)
        for blocker_id in ticket.blocked_by:
            try:
                blocker = self._tickets.get(blocker_id)
                blocker_text = f"BLOCKER {blocker.id}\\nGoal: {blocker.goal_text}"
                blocker_tokens = self._estimate_tokens(blocker_text)
                sections.append({
                    "type": "blocker",
                    "id": blocker.id,
                    "score": 0.95,
                    "tokens": blocker_tokens,
                    "content": blocker.model_dump(mode="json")
                })
                total_tokens += blocker_tokens
            except Exception:
                pass
                
        # Candidate items for budget
        candidates = []
        
        # 3. Direct ADRs
        for adr in self._adrs.list():
            if ticket.id in adr.linked_tickets:
                score = 0.90 + min(len(set(adr.tags) & set(ticket.tags)) * 0.05, 0.15)
                candidates.append({
                    "type": "direct_adr",
                    "id": adr.id,
                    "score": score,
                    "entity": adr
                })
            elif adr.status == ADRStatus.ACCEPTED and set(adr.tags) & set(ticket.tags):
                # 5. Tag ADRs
                score = 0.45 + min(len(set(adr.tags) & set(ticket.tags)) * 0.05, 0.15)
                candidates.append({
                    "type": "tag_adr",
                    "id": adr.id,
                    "score": score,
                    "entity": adr
                })
        
        # 4. Epic
        if ticket.epic:
            try:
                epic = self._epics.get(ticket.epic)
                epic_desc = self._epics.describe(ticket.epic)
                score = 0.50 + min(len(set(epic.tags) & set(ticket.tags)) * 0.05, 0.15)
                candidates.append({
                    "type": "epic",
                    "id": epic.id,
                    "score": score,
                    "entity": epic,
                    "desc": epic_desc
                })
            except Exception:
                pass
                
        # 6. Conventions
        conv_path = self.root / CONTEXT_DIR / "conventions.md"
        if conv_path.exists():
            text = conv_path.read_text(encoding="utf-8")
            # First 300 tokens approx 1200 chars
            excerpt = text[:1200]
            candidates.append({
                "type": "convention",
                "id": "conventions.md",
                "score": 0.30,
                "content": excerpt
            })
            
        # Sort candidates by score descending
        candidates.sort(key=lambda c: c["score"], reverse=True)
        
        for cand in candidates:
            if "content" in cand:
                content_obj = cand["content"]
                text_to_measure = str(content_obj)
            else:
                content_obj = cand.get("desc", cand["entity"].model_dump(mode="json"))
                text_to_measure = str(content_obj)
                
            tokens = self._estimate_tokens(text_to_measure)
            if total_tokens + tokens <= budget:
                sections.append({
                    "type": cand["type"],
                    "id": cand["id"],
                    "score": cand["score"],
                    "tokens": tokens,
                    "content": content_obj
                })
                total_tokens += tokens
            else:
                excluded.append({
                    "id": cand["id"],
                    "reason": "budget"
                })
                
        return {
            "ticket_id": ticket.id,
            "tokens_used": total_tokens,
            "budget": budget,
            "sections": sections,
            "excluded": excluded
        }
