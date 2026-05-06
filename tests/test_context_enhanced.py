import pytest
from karya.core.models import ADRStatus

def test_scoped_context(client):
    # 1. Setup environment
    client.create_ticket("T1", context="C1", labels=["auth"], epic="EPIC-001")
    epic = client.create_epic("Security Epic", goal="Secure it")
    client.update_epic(epic.id, {"success_metrics": ["M1"]})
    client.create_adr("Auth ADR", context="AC", decision="AD", tags=["auth"])
    client.accept_adr("ADR-001")
    
    # Create a dummy conventions file
    conv_dir = client.root / ".karya" / "context"
    conv_dir.mkdir(parents=True, exist_ok=True)
    (conv_dir / "conventions.md").write_text("Standard conventions", encoding="utf-8")
    
    # 2. Load context for ticket
    ctx = client.load_context_for_ticket("TICKET-001")
    
    assert "Scoped for: TICKET-001" in ctx
    assert "auth" in ctx
    assert "Standard conventions" in ctx
    assert "ADR-001: Auth ADR" in ctx
    assert "Epic Context: EPIC-001" in ctx
    assert "Secure it" in ctx

def test_exec_with_enhanced_context(client):
    client.create_ticket("T1", labels=["auth"])
    client.create_adr("Auth ADR", context="AC", decision="AD", tags=["auth"])
    client.accept_adr("ADR-001")
    
    # Move to todo so it's eligible for next/exec
    client.transition("TICKET-001", "todo")
    
    # In click tests we'd use runner, but let's check SDK side if possible 
    # Or just assume CLI works if SDK logic is correct.
    # Let's check the client logic used in exec_cmd.
    
    # Simulate exec logic
    ticket = client.get_next_ticket("test-agent")
    assert ticket.id == "TICKET-001"
    
    context = client.load_context_for_ticket(ticket.id)
    assert "ADR-001" in context
