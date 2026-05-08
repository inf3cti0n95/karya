"""Edge cases for services."""

import pytest
from karya.services.ticket_service import TicketService
from karya.exceptions import TicketNotFoundError, IncompleteAcceptanceCriteria, ValidationError

def test_ticket_service_not_found(tmp_path):
    svc = TicketService(tmp_path)
    with pytest.raises(TicketNotFoundError):
        svc.get("TICKET-999")

def test_ticket_service_done_incomplete_ac(tmp_path):
    svc = TicketService(tmp_path)
    t = svc.create("T1")
    svc.transition(t.id, "todo")
    svc.transition(t.id, "in-progress")
    
    # Add incomplete AC
    t = svc.get(t.id)
    t.acceptance_criteria = [{"text": "AC1", "done": False}]
    svc._save(t)
    
    with pytest.raises(IncompleteAcceptanceCriteria):
        svc.transition(t.id, "done")

def test_ticket_service_invalid_update(tmp_path):
    svc = TicketService(tmp_path)
    t = svc.create("T1")
    with pytest.raises(ValidationError):
        svc.update(t.id, {"non_existent_field": "val"})

def test_ticket_service_list_empty(tmp_path):
    svc = TicketService(tmp_path)
    assert svc.list() == []
