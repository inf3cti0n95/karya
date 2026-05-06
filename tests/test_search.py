import pytest
from datetime import date
from karya.services.index_service import normalize_tag

def test_tag_normalization():
    assert normalize_tag("Auth Service") == "auth-service"
    assert normalize_tag("JWT_token") == "jwt-token"
    assert normalize_tag("PostgreSQL!!") == "postgresql"
    assert normalize_tag("  Multiple---Hyphens  ") == "multiple-hyphens"

def test_search_infrastructure(client):
    # 1. Create entities with tags and content
    client.create_ticket("Build auth service", context="Implement JWT", labels=["auth", "jwt"])
    client.create_epic("Security Epic", goal="Secure the app", tags=["security", "auth"])
    client.create_adr("Use PostgreSQL", context="DB needed", decision="Postgres chosen", tags=["database", "postgresql"])
    
    # 2. Rebuild index
    stats = client.rebuild_index()
    assert stats["indexed"] >= 3
    assert stats["tags"] >= 5
    
    # 3. Search by query
    results = client.search("JWT")
    assert results.total >= 1
    assert results.results[0].id == "TICKET-001"
    
    # 4. Search by tag
    results = client.search("service", tags=["auth"])
    assert results.total >= 1
    assert "auth" in results.results[0].tags
    
    # 5. Search by type
    results = client.search("Postgres", entity_type="adr")
    assert results.total == 1
    assert results.results[0].entity_type == "adr"
    
    # 6. Find related
    results = client.find_related("TICKET-001")
    # Should find Security Epic due to 'auth' tag
    assert any(r.id == "EPIC-001" for r in results.results)

def test_tag_cloud(client):
    client.create_ticket("T1", labels=["tag1", "tag2"])
    client.create_ticket("T2", labels=["tag1"])
    client.rebuild_index()
    
    cloud = client.get_tags()
    assert cloud["tag1"] == 2
    assert cloud["tag2"] == 1
    
    entity_tags = client.get_tags("TICKET-001")
    assert "tag1" in entity_tags["TICKET-001"]
    assert "tag2" in entity_tags["TICKET-001"]

def test_incremental_update(client):
    client.create_ticket("Initial title", labels=["old"])
    client.rebuild_index()
    
    # Verify initial search
    assert client.search("Initial").total == 1
    
    # Update entity
    client.update_ticket("TICKET-001", {"title": "Updated title", "labels": ["new"]})
    
    # Service calls update_entity which we implemented as a rebuild for now
    results = client.search("Updated")
    assert results.total == 1
    assert results.results[0].title == "Updated title"
    assert "new" in results.results[0].tags
    assert "old" not in results.results[0].tags
