"""Search service using SQLite FTS5."""

from pathlib import Path
from typing import Dict, Any, List

from runnrr.core.filesystem import normalize_root
from runnrr.core.db import search, find_related, rebuild_index

class SearchService:
    def __init__(self, root: Path):
        self.root = normalize_root(root)

    def rebuild_index(self) -> None:
        rebuild_index(self.root)

    def search(self, query: str) -> List[Dict[str, Any]]:
        return search(self.root, query)
        
    def find_related(self, entity_id: str) -> List[Dict[str, Any]]:
        return find_related(self.root, entity_id)
