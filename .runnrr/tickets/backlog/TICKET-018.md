# TICKET-018: Remove public DB access in SDK

## Goal
Encapsulate the storage layer by making the `Database` object private within `RunnrrClient`, ensuring that all interactions go through high-level service methods.

## Tasks
- [ ] Rename `RunnrrClient._db` or ensure it's not accessible publicly.
- [ ] Verify that all existing code uses service methods (`self._tickets`, `self._epics`, etc.) instead of direct DB access.

## Acceptance Criteria
- [ ] `RunnrrClient` does not expose the `Database` object in its public interface.
- [ ] The storage implementation is successfully hidden from SDK consumers.
