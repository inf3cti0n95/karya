import pytest
from datetime import date
from karya.core.models import ADRStatus
from karya.exceptions import ADRFrozenError, ADRNotFoundError

def test_adr_create(client):
    adr = client.create_adr(
        title="Use PostgreSQL",
        context="Need a relational DB",
        decision="We chose PostgreSQL for ACID guarantees",
        tags=["database", "postgresql"]
    )
    assert adr.id == "ADR-001"
    assert adr.status == ADRStatus.PROPOSED
    assert adr.title == "Use PostgreSQL"
    assert adr.tags == ["database", "postgresql"]
    assert adr.path.exists()

def test_adr_get(client):
    client.create_adr(title="T1", context="C1", decision="D1")
    adr = client.get_adr("ADR-001")
    assert adr.title == "T1"

def test_adr_accept(client):
    client.create_adr(title="T1", context="C1", decision="D1")
    client.accept_adr("ADR-001")
    adr = client.get_adr("ADR-001")
    assert adr.status == ADRStatus.ACCEPTED

def test_adr_frozen_after_accept(client):
    client.create_adr(title="T1", context="C1", decision="D1")
    client.accept_adr("ADR-001")
    
    with pytest.raises(ADRFrozenError):
        client._adrs.update("ADR-001", {"decision_text": "new decision"})
    
    # Non-frozen field should work
    client._adrs.update("ADR-001", {"tags": ["new-tag"]})
    adr = client.get_adr("ADR-001")
    assert "new-tag" in adr.tags

def test_adr_supersede(client):
    client.create_adr(title="Old DB", context="C1", decision="Use SQLite")
    client.accept_adr("ADR-001")
    
    new_adr = client.supersede_adr(
        "ADR-001", 
        new_title="New DB", 
        context="Scale needs changed", 
        decision="Use PostgreSQL"
    )
    
    assert new_adr.id == "ADR-002"
    assert new_adr.supersedes == "ADR-001"
    
    old_adr = client.get_adr("ADR-001")
    assert old_adr.status == ADRStatus.SUPERSEDED
    assert old_adr.superseded_by == "ADR-002"

def test_adr_deprecate(client):
    client.create_adr(title="T1", context="C1", decision="D1")
    client.accept_adr("ADR-001")
    client.deprecate_adr("ADR-001", reason="No longer needed")
    
    adr = client.get_adr("ADR-001")
    assert adr.status == ADRStatus.DEPRECATED

def test_adr_link_ticket(client):
    client.create_ticket("Ticket 1")
    client.create_adr(title="ADR 1", context="C1", decision="D1")
    
    client.link_adr_ticket("ADR-001", "TICKET-001")
    
    adr = client.get_adr("ADR-001")
    assert "TICKET-001" in adr.linked_tickets
    
    ticket = client.get_ticket("TICKET-001")
    assert "ADR-001" in ticket.linked_adrs

def test_adr_link_epic(client):
    client.create_epic("Epic 1")
    client.create_adr(title="ADR 1", context="C1", decision="D1")
    
    client.link_adr_epic("ADR-001", "EPIC-001")
    
    adr = client.get_adr("ADR-001")
    assert "EPIC-001" in adr.linked_epics
    
    epic = client.get_epic("EPIC-001")
    assert "ADR-001" in epic.linked_adrs

def test_adr_list(client):
    client.create_adr(title="A1", context="C", decision="D", tags=["tag1"])
    client.create_adr(title="A2", context="C", decision="D", tags=["tag2"])
    client.accept_adr("ADR-001")
    
    all_adrs = client.list_adrs()
    assert len(all_adrs) == 2
    
    accepted = client.list_adrs(status="accepted")
    assert len(accepted) == 1
    assert accepted[0].id == "ADR-001"
    
    tagged = client.list_adrs(tag="tag2")
    assert len(tagged) == 1
    assert tagged[0].id == "ADR-002"
