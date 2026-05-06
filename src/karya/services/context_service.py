"""Enhanced context service for scoped bundles."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from karya.core.filesystem import CONTEXT_DIR, load_context_files, normalize_root
from karya.core.models import ADRStatus
from karya.services.adr_service import ADRService
from karya.services.epic_service import EpicService
from karya.services.index_service import IndexService
from karya.services.ticket_service import TicketService


class ContextService:
	def __init__(self, root: Path):
		self.root = normalize_root(root)
		# services are initialized on demand to avoid circular deps during __init__ if any
		self._ticket_service: TicketService | None = None
		self._adr_service: ADRService | None = None
		self._epic_service: EpicService | None = None
		self._index_service: IndexService | None = None

	@property
	def _tickets(self) -> TicketService:
		if not self._ticket_service:
			self._ticket_service = TicketService(self.root)
		return self._ticket_service

	@property
	def _adrs(self) -> ADRService:
		if not self._adr_service:
			self._adr_service = ADRService(self.root)
		return self._adr_service

	@property
	def _epics(self) -> EpicService:
		if not self._epic_service:
			self._epic_service = EpicService(self.root)
		return self._epic_service

	@property
	def _index(self) -> IndexService:
		if not self._index_service:
			self._index_service = IndexService(self.root)
		return self._index_service

	def load_for_ticket(self, ticket_id: str, max_tokens: int = 4000) -> str:
		"""Build a context bundle scoped to a specific ticket."""
		ticket = self._tickets.get(ticket_id)
		tags = ticket.labels # normalized tags

		bundle = []
		bundle.append("---")
		bundle.append("# Karya Context Bundle")
		bundle.append(f"# Scoped for: {ticket_id} | Tags: {', '.join(tags)}")
		bundle.append(f"# Generated: {datetime.now(timezone.utc).isoformat()}")
		bundle.append("")

		# 1. Conventions
		bundle.append("## Conventions")
		bundle.append(self.load_conventions())
		bundle.append("")

		# 2. Relevant ADRs
		relevant_adrs = self._adrs.list(status=ADRStatus.ACCEPTED)
		# Rank by tag overlap
		ranked_adrs = []
		for adr in relevant_adrs:
			overlap = set(tags).intersection(set(adr.tags))
			if overlap:
				ranked_adrs.append((len(overlap), adr))
		
		ranked_adrs.sort(key=lambda x: x[0], reverse=True)

		if ranked_adrs:
			bundle.append("## Relevant Architecture Decisions")
			bundle.append("")
			for _, adr in ranked_adrs:
				bundle.append(f"### {adr.id}: {adr.title} [{adr.status.value}]")
				bundle.append(f"**Context:** {adr.context_text or 'N/A'}")
				bundle.append(f"**Decision:** {adr.decision_text or 'N/A'}")
				bundle.append("")

		# 3. Epic Context
		if ticket.epic:
			try:
				epic = self._epics.get(ticket.epic)
				bundle.append(f"## Epic Context: {epic.id} — {epic.title}")
				bundle.append(f"**Goal:** {epic.goal_text or 'N/A'}")
				if epic.success_metrics:
					bundle.append("**Success Metrics:**")
					for m in epic.success_metrics:
						bundle.append(f"- {m}")
				bundle.append("")
			except Exception:
				pass

		bundle.append("---")
		return "\n".join(bundle)

	def load_all(self) -> str:
		"""Load everything: all static context files + all accepted ADRs."""
		static = load_context_files(self.root)
		adrs = self.load_adrs(status=ADRStatus.ACCEPTED)
		
		return f"{static}\n\n---\n\n## Architecture Decisions\n\n{adrs}"

	def load(self) -> str:
		"""Backward compatibility with Phase 1-17."""
		return self.load_all()

	def load_conventions(self) -> str:
		conv_path = self.root / CONTEXT_DIR / "conventions.md"
		if conv_path.exists():
			return conv_path.read_text(encoding="utf-8")
		return "No conventions defined."

	def load_adrs(self, status: ADRStatus = ADRStatus.ACCEPTED, tags: list[str] | None = None) -> str:
		adrs = self._adrs.list(status=status)
		if tags:
			adrs = [adr for adr in adrs if any(t in tags for t in adr.tags)]
		
		output = []
		for adr in adrs:
			output.append(f"### {adr.id}: {adr.title} [{adr.status.value}]")
			output.append(adr.decision_text or "")
			output.append("")
		
		return "\n".join(output)
