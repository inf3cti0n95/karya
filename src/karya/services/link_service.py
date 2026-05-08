"""Link service for managing bidirectional relationships."""

from pathlib import Path

from karya.core.filesystem import normalize_root
from karya.services.ticket_service import TicketService
from karya.services.epic_service import EpicService
from karya.services.adr_service import ADRService
from karya.exceptions import KaryaError

class LinkService:
    def __init__(self, root: Path):
        self.root = normalize_root(root)
        self._tickets = TicketService(self.root)
        self._epics = EpicService(self.root)
        self._adrs = ADRService(self.root)

    def link(self, source_id: str, target_id: str, actor: str | None = None) -> None:
        # Determine types based on prefixes
        src_type = self._get_type(source_id)
        tgt_type = self._get_type(target_id)
        
        if src_type == "ticket" and tgt_type == "adr":
            self._link_ticket_adr(source_id, target_id, actor)
        elif src_type == "adr" and tgt_type == "ticket":
            self._link_ticket_adr(target_id, source_id, actor)
        elif src_type == "ticket" and tgt_type == "epic":
            self._link_ticket_epic(source_id, target_id, actor)
        elif src_type == "epic" and tgt_type == "ticket":
            self._link_ticket_epic(target_id, source_id, actor)
        elif src_type == "adr" and tgt_type == "epic":
            self._link_adr_epic(source_id, target_id, actor)
        elif src_type == "epic" and tgt_type == "adr":
            self._link_adr_epic(target_id, source_id, actor)
        else:
            raise KaryaError(f"Linking {src_type} to {tgt_type} is not supported.")

    def _get_type(self, entity_id: str) -> str:
        if entity_id.startswith("TICKET-"):
            return "ticket"
        if entity_id.startswith("EPIC-"):
            return "epic"
        if entity_id.startswith("ADR-"):
            return "adr"
        raise KaryaError(f"Unknown entity format: {entity_id}")

    def _link_ticket_adr(self, ticket_id: str, adr_id: str, actor: str | None) -> None:
        ticket = self._tickets.get(ticket_id)
        adr = self._adrs.get(adr_id)
        
        if adr_id not in ticket.linked_adrs:
            ticket.linked_adrs.append(adr_id)
            self._tickets.update(ticket_id, {"linked_adrs": ticket.linked_adrs}, actor)
            
        if ticket_id not in adr.linked_tickets:
            adr.linked_tickets.append(ticket_id)
            self._adrs.update(adr_id, {"linked_tickets": adr.linked_tickets}, actor)

    def _link_ticket_epic(self, ticket_id: str, epic_id: str, actor: str | None) -> None:
        ticket = self._tickets.get(ticket_id)
        epic = self._epics.get(epic_id)
        
        if ticket.epic != epic_id:
            self._tickets.update(ticket_id, {"epic": epic_id}, actor)
            
    def _link_adr_epic(self, adr_id: str, epic_id: str, actor: str | None) -> None:
        adr = self._adrs.get(adr_id)
        epic = self._epics.get(epic_id)
        
        if epic_id not in adr.linked_epics:
            adr.linked_epics.append(epic_id)
            self._adrs.update(adr_id, {"linked_epics": adr.linked_epics}, actor)
            
        if adr_id not in epic.linked_adrs:
            epic.linked_adrs.append(adr_id)
            self._epics.update(epic_id, {"linked_adrs": epic.linked_adrs}, actor)
