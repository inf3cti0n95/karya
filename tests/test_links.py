import pytest

def test_link_ticket_epic(client):
    client.create_ticket("T1")
    client.create_epic("E1")
    
    client.link("ticket", "TICKET-001", "epic", "EPIC-001")
    
    links = client.get_links("TICKET-001")
    assert links["epic"][0]["id"] == "EPIC-001"
    
    links = client.get_links("EPIC-001")
    assert any(t["id"] == "TICKET-001" for t in links["tickets"])

def test_link_ticket_adr(client):
    client.create_ticket("T1")
    client.create_adr("A1", context="C", decision="D")
    
    client.link("ticket", "TICKET-001", "adr", "ADR-001")
    
    links = client.get_links("TICKET-001")
    assert links["adrs"][0]["id"] == "ADR-001"
    
    links = client.get_links("ADR-001")
    assert any(t["id"] == "TICKET-001" for t in links["tickets"])

def test_link_epic_adr(client):
    client.create_epic("E1")
    client.create_adr("A1", context="C", decision="D")
    
    client.link("epic", "EPIC-001", "adr", "ADR-001")
    
    links = client.get_links("EPIC-001")
    assert links["adrs"][0]["id"] == "ADR-001"
    
    links = client.get_links("ADR-001")
    assert any(e["id"] == "EPIC-001" for e in links["epics"])

def test_unlink_ticket_epic(client):
    client.create_ticket("T1")
    client.create_epic("E1")
    client.link("ticket", "TICKET-001", "epic", "EPIC-001")
    
    # Verify linked
    assert client.get_links("TICKET-001")["epic"][0]["id"] == "EPIC-001"
    
    # Unlink
    client._links.unlink("ticket", "TICKET-001", "epic", "EPIC-001")
    
    links = client.get_links("TICKET-001")
    assert not links["epic"]
    
    links = client.get_links("EPIC-001")
    assert not any(t["id"] == "TICKET-001" for t in links["tickets"])
