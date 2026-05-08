"""Service-level unit tests for Phase A."""

import pytest
from pathlib import Path
from karya.services.ticket_service import TicketService
from karya.services.epic_service import EpicService
from karya.services.adr_service import ADRService
from karya.core.models import TicketStatus, ADRStatus

@pytest.fixture
def ticket_service(tmp_path):
    return TicketService(tmp_path)

@pytest.fixture
def epic_service(tmp_path):
    return EpicService(tmp_path)

@pytest.fixture
def adr_service(tmp_path):
    return ADRService(tmp_path)

def test_ticket_service_lifecycle(ticket_service):
    ticket = ticket_service.create("Test Ticket", goal="Finish it")
    assert ticket.id == "TICKET-001"
    assert ticket.status == TicketStatus.BACKLOG
    
    ticket_service.transition(ticket.id, "todo")
    ticket = ticket_service.get(ticket.id)
    assert ticket.status == TicketStatus.TODO
    
    ticket_service.transition(ticket.id, "in-progress")
    ticket_service.log(ticket.id, "I am working")
    ticket = ticket_service.get(ticket.id)
    assert len(ticket.execution_log) == 1
    assert "working" in ticket.execution_log[0]["message"]

def test_epic_service_progress(ticket_service, epic_service):
    epic = epic_service.create("Main Epic")
    t1 = ticket_service.create("T1", epic=epic.id)
    t2 = ticket_service.create("T2", epic=epic.id)
    
    # Both backlog -> planned
    desc = epic_service.describe(epic.id)
    assert desc["status"] == "planned"
    assert desc["progress"]["total"] == 2
    assert desc["progress"]["done"] == 0
    
    # One in-progress -> active
    ticket_service.transition(t1.id, "todo")
    ticket_service.transition(t1.id, "in-progress")
    desc = epic_service.describe(epic.id)
    assert desc["status"] == "active"
    
    # All done -> done
    ticket_service.transition(t1.id, "done")
    ticket_service.transition(t2.id, "todo")
    ticket_service.transition(t2.id, "done")
    desc = epic_service.describe(epic.id)
    assert desc["status"] == "done"
    assert desc["progress"]["percent"] == 100

def test_adr_service_lifecycle(adr_service):
    adr = adr_service.create("Decision", context="C", decision="D")
    assert adr.status == ADRStatus.PROPOSED
    
    adr_service.accept(adr.id)
    adr = adr_service.get(adr.id)
    assert adr.status == ADRStatus.ACCEPTED
