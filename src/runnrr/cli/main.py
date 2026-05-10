"""Command-line interface for Runnrr."""

from __future__ import annotations

import json
from typing import Any, Dict, List
from io import StringIO
import sys

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown

from runnrr.core.models import EpicType, Priority, TicketType
from runnrr.exceptions import (
    IncompleteAcceptanceCriteria,
    InvalidTransitionError,
    TicketNotFoundError,
    ValidationError,
)
from runnrr.sdk.client import RunnrrClient


def _emit(payload: Dict[str, Any], use_json: bool) -> None:
    if use_json:
        sys.stdout.write(json.dumps(payload) + "\n")
        sys.stdout.flush()
    else:
        # Re-route stdout for capture by CliRunner
        stdout = sys.stdout
        if "pytest" in sys.modules:
            # When running tests, CliRunner replaces sys.stdout with a buffer
            pass
        
        console = Console(file=stdout, force_terminal=True, width=100)
        _render_human_with_console(payload, console)


def ok(use_json: bool, **kwargs: Any) -> None:
    _emit({"status": "ok", **kwargs}, use_json)


def err(use_json: bool, code: str, message: str, **kwargs: Any) -> None:
    _emit({"status": "error", "code": code, "message": message, **kwargs}, use_json)
    sys.exit(1)


def _get_client(agent: str | None = None, db_path: str | None = None) -> RunnrrClient:
    return RunnrrClient(".", agent=agent, db_path=db_path)


@click.group(add_help_option=False, invoke_without_command=True)
@click.option("--help", "show_help", is_flag=True, help="Show help")
@click.option("--json", "use_json", is_flag=True, help="Use JSON output")
@click.option("--db-path", help="Explicit path to runnrr.db")
@click.pass_context
def cli(ctx: click.Context, show_help: bool, use_json: bool, db_path: str | None) -> None:
    ctx.ensure_object(dict)
    ctx.obj["json"] = use_json
    ctx.obj["db_path"] = db_path
    
    # We'll use a cleanup callback to close the client
    @ctx.call_on_close
    def cleanup():
        if "client" in ctx.obj:
            ctx.obj["client"].close()

    if show_help or ctx.invoked_subcommand is None:  # pragma: no cover
        console = Console(force_terminal=True, width=100)
        console.print(Panel("Runnrr - filesystem-native agent workspace protocol", title="Runnrr"))
        console.print("\n[bold]Primary Interface:[/bold]")
        console.print("  runnrr list        # what should I work on? (Default: actionable)")
        console.print("  runnrr context     # what do I need to know?")
        console.print("  runnrr log         # what did I just do?")
        console.print("  runnrr update      # update ticket content, tasks, and ACs")
        console.print("  runnrr done        # I finished this")
        console.print("  runnrr status      # workspace health & stats")
        ctx.exit(0)


@cli.command("init")
@click.pass_context
def init_cmd(ctx: click.Context) -> None:
    client = _get_client()
    client.init()
    
    from runnrr.core.filesystem import find_host_gitignore, RUNNRR_ROOT
    host_gitignore = find_host_gitignore(client.root)
    
    if not ctx.obj["json"]:
        if host_gitignore:
            click.echo(f"Added {RUNNRR_ROOT}/ to {host_gitignore}")
        else:
            click.echo(f"Note: no .gitignore found. Add {RUNNRR_ROOT}/ manually if using git.")
            
    ok(ctx.obj["json"], path=".runnrr", initialized=True)


@cli.command("status")
@click.pass_context
def status_cmd(ctx: click.Context) -> None:
    """Check workspace status and health."""
    client = _get_client()
    try:
        # We need a get_status_info method in client
        info = client.get_status_info()
        ok(ctx.obj["json"], **info)
    except Exception as e:
        err(ctx.obj["json"], "ERROR", str(e))


@cli.command("migrate")
@click.option("--force", is_flag=True, help="Force migration even if DB already has data.")
@click.pass_context
def migrate_cmd(ctx: click.Context, force: bool) -> None:
    """Migrate from v0.1.x markdown files to SQLite database."""
    client = _get_client()
    try:
        result = client.migrate(force=force)
        ok(ctx.obj["json"], **result)
    except Exception as e:
        err(ctx.obj["json"], "MIGRATION_ERROR", str(e))


@cli.command("events")
@click.option("--ticket", help="Filter events for a specific ticket.")
@click.option("--epic", help="Filter events for a specific epic.")
@click.option("--adr", help="Filter events for a specific ADR.")
@click.option("--since", help="Filter events since a certain date (ISO8601).")
@click.option("--limit", default=20, type=int, help="Limit number of events shown.")
@click.pass_context
def events_cmd(ctx: click.Context, ticket: str | None, epic: str | None, adr: str | None, since: str | None, limit: int) -> None:
    """View event log (audit trail)."""
    client = _get_client()
    try:
        # We need a list_events method in client
        events = client.list_events(ticket=ticket, epic=epic, adr=adr, since=since, limit=limit)
        ok(ctx.obj["json"], count=len(events), events=events)
    except Exception as e:
        err(ctx.obj["json"], "ERROR", str(e))


@cli.command("export")
@click.argument("entity_id", required=False)
@click.option("--all", "export_all", is_flag=True, help="Export all entities.")
@click.option("--out", help="Output file or directory.")
@click.pass_context
def export_cmd(ctx: click.Context, entity_id: str | None, export_all: bool, out: str | None) -> None:
    """Export entities as markdown."""
    client = _get_client()
    try:
        if export_all:
            # We need export_all method in client
            results = client.export_all(out_dir=out)
            ok(ctx.obj["json"], **results)
        elif entity_id:
            content = client.export_entity(entity_id, out_file=out)
            if not out:
                click.echo(content)
            else:
                ok(ctx.obj["json"], path=out, message=f"Exported to {out}")
        else:
            err(ctx.obj["json"], "INVALID_OPTION", "Must specify entity ID or --all")
    except Exception as e:
        err(ctx.obj["json"], "ERROR", str(e))


@cli.command("create")
@click.argument("title")
@click.option("--type", "type_", default="feature")
@click.option("--priority", default="medium")
@click.option("--epic", default=None)
@click.option("--tag", "tags", multiple=True)
@click.option("--effort", default=1, type=int)
@click.option("--goal", default="")
@click.pass_context
def create_cmd(
    ctx: click.Context,
    title: str,
    type_: str,
    priority: str,
    epic: str | None,
    tags: List[str],
    effort: int,
    goal: str,
) -> None:
    client = _get_client()
    try:
        ticket_type = TicketType(type_.lower())
        priority_value = Priority(priority.lower())
    except ValueError as exc:  # pragma: no cover
        err(ctx.obj["json"], "INVALID_OPTION", str(exc))
    
    ticket = client.create_ticket(
        title=title,
        goal=goal,
        type=ticket_type,
        priority=priority_value,
        epic=epic,
        tags=list(tags),
        estimated_effort=effort,
    )

    ok(
        ctx.obj["json"],
        ticket={
            "id": ticket.id,
            "title": ticket.title,
            "status": ticket.status.value,
        },
    )


@cli.command("list")
@click.option("--status", help="Filter by status (todo, in-progress, backlog, blocked, done, all, actionable).")
@click.option("--epic", help="Filter by epic ID.")
@click.option("--tag", help="Filter by tag.")
@click.option("--blocked", is_flag=True, help="Show only blocked tickets and their blockers.")
@click.pass_context
def list_cmd(
    ctx: click.Context, status: str | None, epic: str | None, tag: str | None, blocked: bool
) -> None:
    """List tickets."""
    client = _get_client()
    
    if blocked:
        status = "blocked"
        
    tickets = client.list_tickets(status=status, epic=epic, tag=tag)
    summary = client.get_summary()

    payload = [
        {
            "id": ticket.id,
            "title": ticket.title,
            "status": ticket.status.value,
            "priority": ticket.priority.value,
            "tags": ticket.tags,
            "epic_id": ticket.epic,
            "owner": ticket.owner,
            "tasks_total": len(ticket.tasks),
            "tasks_done": len([t for t in ticket.tasks if t.get('done')]),
            "criteria_total": len(ticket.acceptance_criteria),
            "criteria_done": len([c for c in ticket.acceptance_criteria if c.get('done')]),
            "blocked_by": ticket.blocked_by,
        }
        for ticket in tickets
    ]
    
    # If blocked, we need blockers info
    if blocked:
        for p in payload:
            # We need to get titles/statuses for the blockers
            blocker_ids = p.get("blocked_by", [])
            p["blocked_by_detail"] = []
            for b_id in blocker_ids:
                try:
                    b_ticket = client.get_ticket(b_id)
                    p["blocked_by_detail"].append({
                        "id": b_ticket.id,
                        "title": b_ticket.title,
                        "status": b_ticket.status.value
                    })
                except Exception:
                    p["blocked_by_detail"].append({"id": b_id, "title": "Unknown", "status": "unknown"})

    ok(ctx.obj["json"], showing=status or "actionable", count=len(payload), tickets=payload, summary=summary)


@cli.command("context")
@click.argument("ticket_id")
@click.option("--budget", default=4000, type=int)
@click.pass_context
def context_cmd(
    ctx: click.Context, ticket_id: str, budget: int
) -> None:
    client = _get_client()
    try:
        context_data = client.build_context(ticket_id, budget=budget)
    except TicketNotFoundError as exc:
        err(ctx.obj["json"], "NOT_FOUND", str(exc))
    except Exception as exc:
        err(ctx.obj["json"], "ERROR", str(exc))

    ok(ctx.obj["json"], **context_data)


@cli.command("start")
@click.argument("ticket_id")
@click.pass_context
def start_cmd(ctx: click.Context, ticket_id: str) -> None:
    client = _get_client()
    try:
        ticket = client.get_ticket(ticket_id)
        previous = ticket.status.value
        if previous == "backlog":
            client.transition(ticket_id, "todo")
        client.transition(ticket_id, "in-progress")
    except TicketNotFoundError as exc:
        err(ctx.obj["json"], "NOT_FOUND", str(exc))
    except InvalidTransitionError as exc:
        err(ctx.obj["json"], "INVALID_TRANSITION", str(exc))

    ok(
        ctx.obj["json"],
        ticket_id=ticket_id,
        previous_state=previous,
        new_state="in-progress",
    )


@cli.command("done")
@click.argument("ticket_id")
@click.pass_context
def done_cmd(ctx: click.Context, ticket_id: str) -> None:
    client = _get_client()
    try:
        ticket = client.transition(ticket_id, "done")
    except IncompleteAcceptanceCriteria as exc:
        err(
            ctx.obj["json"],
            "INCOMPLETE_CRITERIA",
            "Acceptance criteria incomplete.",
            unchecked=exc.unchecked,
        )
    except Exception as exc:
        err(ctx.obj["json"], "ERROR", str(exc))

    ok(
        ctx.obj["json"],
        ticket_id=ticket.id,
        new_state=ticket.status.value,
    )


@cli.command("block")
@click.argument("ticket_id")
@click.argument("reason")
@click.pass_context
def block_cmd(ctx: click.Context, ticket_id: str, reason: str) -> None:
    client = _get_client()
    try:
        client.block(ticket_id, reason)
    except Exception as exc:
        err(ctx.obj["json"], "ERROR", str(exc))

    ok(ctx.obj["json"], ticket_id=ticket_id, new_state="blocked", reason=reason)


@cli.command("log")
@click.argument("ticket_id")
@click.argument("message")
@click.pass_context
def log_cmd(ctx: click.Context, ticket_id: str, message: str) -> None:
    client = _get_client()
    try:
        ticket = client.log(ticket_id, message)
    except Exception as exc:
        err(ctx.obj["json"], "ERROR", str(exc))

    ok(
        ctx.obj["json"],
        ticket_id=ticket_id,
        message="logged",
        entry_count=len(ticket.execution_log),
    )


@cli.command("update")
@click.argument("ticket_id")
@click.option("--goal", help="Update the ticket goal.")
@click.option("--notes", help="Update the ticket notes.")
@click.option("--add-task", help="Add a new task.")
@click.option("--check-task", type=int, help="Check off a task by index (0-based).")
@click.option("--uncheck-task", type=int, help="Uncheck a task by index (0-based).")
@click.option("--add-ac", help="Add a new acceptance criterion.")
@click.option("--check-ac", type=int, help="Check off an AC by index (0-based).")
@click.option("--uncheck-ac", type=int, help="Uncheck an AC by index (0-based).")
@click.option("--tag", "tags", multiple=True, help="Set ticket tags.")
@click.pass_context
def update_cmd(
    ctx: click.Context,
    ticket_id: str,
    goal: str | None,
    notes: str | None,
    add_task: str | None,
    check_task: int | None,
    uncheck_task: int | None,
    add_ac: str | None,
    check_ac: int | None,
    uncheck_ac: int | None,
    tags: List[str],
) -> None:
    """Update a ticket's content."""
    client = _get_client()
    try:
        updates = {}
        if goal is not None:
            updates["goal"] = goal
        if notes is not None:
            updates["notes"] = notes
        if tags:
            updates["tags"] = list(tags)
            
        if updates:
            client.update_ticket(ticket_id, updates)
            
        if add_task:
            client.add_ticket_task(ticket_id, add_task)
        if check_task is not None:
            client.check_ticket_task(ticket_id, check_task)
        if uncheck_task is not None:
            client.uncheck_ticket_task(ticket_id, uncheck_task)
            
        if add_ac:
            client.add_ticket_ac(ticket_id, add_ac)
        if check_ac is not None:
            client.check_ticket_ac(ticket_id, check_ac)
        if uncheck_ac is not None:
            client.uncheck_ticket_ac(ticket_id, uncheck_ac)
            
        ok(ctx.obj["json"], ticket_id=ticket_id, message="updated")
    except Exception as exc:
        err(ctx.obj["json"], "ERROR", str(exc))


@cli.command("describe")
@click.argument("ticket_id")
@click.pass_context
def describe_cmd(ctx: click.Context, ticket_id: str) -> None:
    client = _get_client()
    try:
        description = client.describe_ticket(ticket_id)
    except Exception as exc:
        err(ctx.obj["json"], "NOT_FOUND", str(exc))

    ok(ctx.obj["json"], ticket=description)


@cli.group("epic")
@click.pass_context
def epic_cmd(ctx: click.Context) -> None:
    return None


@epic_cmd.command("create")
@click.argument("title")
@click.option("--type", "type_", default="feature")
@click.option("--priority", default="medium")
@click.option("--goal", default="")
@click.option("--tag", "tags", multiple=True)
@click.pass_context
def epic_create_cmd(
    ctx: click.Context,
    title: str,
    type_: str,
    priority: str,
    goal: str,
    tags: List[str],
) -> None:
    client = _get_client()
    try:
        epic_type = EpicType(type_.lower())
        priority_value = Priority(priority.lower())
    except ValueError as exc:  # pragma: no cover
        err(ctx.obj["json"], "INVALID_OPTION", str(exc))

    epic = client.create_epic(
        title=title,
        type=epic_type,
        priority=priority_value,
        goal=goal,
        tags=list(tags),
    )

    ok(
        ctx.obj["json"],
        epic={
            "id": epic.id,
            "title": epic.title,
        },
    )


@epic_cmd.command("list")
@click.option("--tag", default=None)
@click.pass_context
def epic_list_cmd(
    ctx: click.Context,
    tag: str | None,
) -> None:
    client = _get_client()
    epics = client.list_epics(tag=tag)

    payload = [
        {
            "id": epic.id,
            "title": epic.title,
            "priority": epic.priority.value,
        }
        for epic in epics
    ]

    ok(ctx.obj["json"], count=len(payload), epics=payload)


@epic_cmd.command("describe")
@click.argument("epic_id")
@click.pass_context
def epic_describe_cmd(ctx: click.Context, epic_id: str) -> None:
    client = _get_client()
    try:
        description = client.describe_epic(epic_id)
    except Exception as exc:
        err(ctx.obj["json"], "NOT_FOUND", str(exc))

    ok(ctx.obj["json"], epic=description)


@epic_cmd.command("update")
@click.argument("epic_id")
@click.option("--title", help="Update the epic title.")
@click.option("--goal", help="Update the epic goal.")
@click.option("--notes", help="Update the epic notes.")
@click.option("--metric", "metrics", multiple=True, help="Set success metrics (overwrites existing).")
@click.option("--tag", "tags", multiple=True, help="Set epic tags.")
@click.pass_context
def epic_update_cmd(
    ctx: click.Context,
    epic_id: str,
    title: str | None,
    goal: str | None,
    notes: str | None,
    metrics: List[str],
    tags: List[str],
) -> None:
    """Update an epic's content."""
    client = _get_client()
    try:
        updates = {}
        if title is not None:
            updates["title"] = title
        if goal is not None:
            updates["goal"] = goal
        if notes is not None:
            updates["notes"] = notes
        if metrics:
            updates["success_metrics"] = list(metrics)
        if tags:
            updates["tags"] = list(tags)
            
        if updates:
            client.update_epic(epic_id, updates)
            ok(ctx.obj["json"], epic_id=epic_id, message="updated")
        else:
            err(ctx.obj["json"], "INVALID_OPTION", "No updates provided")
    except Exception as exc:
        err(ctx.obj["json"], "ERROR", str(exc))


@cli.group("adr")
@click.pass_context
def adr_cmd(ctx: click.Context) -> None:
    return None


@adr_cmd.command("create")
@click.argument("title")
@click.option("--context", required=True)
@click.option("--decision", required=True)
@click.option("--consequences", default="")
@click.option("--alternatives", default="")
@click.option("--supersedes", help="ID of the ADR this one supersedes.")
@click.option("--ticket", "linked_tickets", multiple=True)
@click.option("--epic", "linked_epics", multiple=True)
@click.option("--tag", "tags", multiple=True)
@click.pass_context
def adr_create_cmd(
    ctx: click.Context,
    title: str,
    context: str,
    decision: str,
    consequences: str,
    alternatives: str,
    supersedes: str | None,
    linked_tickets: List[str],
    linked_epics: List[str],
    tags: List[str],
) -> None:
    client = _get_client()
    try:
        adr = client.create_adr(
            title=title,
            context=context,
            decision=decision,
            consequences=consequences,
            alternatives=alternatives,
            linked_tickets=list(linked_tickets),
            linked_epics=list(linked_epics),
            tags=list(tags),
        )
        
        if supersedes:
            client.update_adr(adr.id, {"supersedes": supersedes})
            # Also update the superseded ADR
            client.update_adr(supersedes, {"superseded_by": adr.id, "status": "superseded"})

        ok(
            ctx.obj["json"],
            adr={
                "id": adr.id,
                "title": adr.title,
                "status": adr.status.value,
            },
        )
    except Exception as exc:
        err(ctx.obj["json"], "ERROR", str(exc))


@adr_cmd.command("list")
@click.option("--status", default=None)
@click.option("--tag", default=None)
@click.pass_context
def adr_list_cmd(ctx: click.Context, status: str | None, tag: str | None) -> None:
    client = _get_client()
    adrs = client.list_adrs(status=status, tag=tag)

    payload = [
        {
            "id": adr.id,
            "title": adr.title,
            "status": adr.status.value,
            "date": adr.date.isoformat(),
        }
        for adr in adrs
    ]
    ok(ctx.obj["json"], count=len(payload), adrs=payload)


@adr_cmd.command("accept")
@click.argument("adr_id")
@click.pass_context
def adr_accept_cmd(ctx: click.Context, adr_id: str) -> None:
    client = _get_client()
    try:
        adr = client.accept_adr(adr_id)
    except Exception as exc:
        err(ctx.obj["json"], "ACCEPT_FAILED", str(exc))

    ok(ctx.obj["json"], adr_id=adr_id, status=adr.status.value)


@adr_cmd.command("describe")
@click.argument("adr_id")
@click.pass_context
def adr_describe_cmd(ctx: click.Context, adr_id: str) -> None:
    client = _get_client()
    try:
        description = client.describe_adr(adr_id)
    except Exception as exc:
        err(ctx.obj["json"], "NOT_FOUND", str(exc))

    ok(ctx.obj["json"], adr=description)


@adr_cmd.command("update")
@click.argument("adr_id")
@click.option("--title", help="Update the ADR title.")
@click.option("--context", "context_text", help="Update the context.")
@click.option("--decision", "decision_text", help="Update the decision.")
@click.option("--consequences", "consequences_text", help="Update the consequences.")
@click.option("--alternatives", "alternatives_text", help="Update the alternatives.")
@click.option("--tag", "tags", multiple=True, help="Set ADR tags.")
@click.pass_context
def adr_update_cmd(
    ctx: click.Context,
    adr_id: str,
    title: str | None,
    context_text: str | None,
    decision_text: str | None,
    consequences_text: str | None,
    alternatives_text: str | None,
    tags: List[str],
) -> None:
    """Update an ADR's content."""
    client = _get_client()
    try:
        updates = {}
        if title is not None:
            updates["title"] = title
        if context_text is not None:
            updates["context_text"] = context_text
        if decision_text is not None:
            updates["decision_text"] = decision_text
        if consequences_text is not None:
            updates["consequences"] = consequences_text
        if alternatives_text is not None:
            updates["alternatives"] = alternatives_text
        if tags:
            updates["tags"] = list(tags)
            
        if updates:
            client.update_adr(adr_id, updates)
            ok(ctx.obj["json"], adr_id=adr_id, message="updated")
        else:
            err(ctx.obj["json"], "INVALID_OPTION", "No updates provided")
    except Exception as exc:
        err(ctx.obj["json"], "ERROR", str(exc))


@cli.command("search")
@click.argument("query")
@click.pass_context
def search_cmd(ctx: click.Context, query: str) -> None:
    client = _get_client()
    try:
        results = client.search(query)
    except Exception as exc:
        err(ctx.obj["json"], "ERROR", str(exc))
    ok(ctx.obj["json"], count=len(results), results=results)


@cli.command("find-related")
@click.argument("entity_id")
@click.pass_context
def find_related_cmd(ctx: click.Context, entity_id: str) -> None:
    client = _get_client()
    try:
        results = client.find_related(entity_id)
    except Exception as exc:
        err(ctx.obj["json"], "ERROR", str(exc))
    ok(ctx.obj["json"], count=len(results), results=results)


@cli.command("actions")
@click.argument("ticket_id")
@click.pass_context
def actions_cmd(ctx: click.Context, ticket_id: str) -> None:
    client = _get_client()
    try:
        actions = client.valid_actions(ticket_id)
        ticket = client.get_ticket(ticket_id)
    except Exception as exc:
        err(ctx.obj["json"], "ERROR", str(exc))
    ok(ctx.obj["json"], ticket_id=ticket_id, state=ticket.status.value, available=actions)


@cli.command("link")
@click.argument("source_id")
@click.argument("target_id")
@click.pass_context
def link_cmd(ctx: click.Context, source_id: str, target_id: str) -> None:
    client = _get_client()
    try:
        client.link(source_id, target_id)
    except Exception as exc:
        err(ctx.obj["json"], "ERROR", str(exc))
    ok(ctx.obj["json"], source=source_id, target=target_id)


@cli.group("index")
@click.pass_context
def index_cmd(ctx: click.Context) -> None:
    return None

@index_cmd.command("rebuild")
@click.pass_context
def index_rebuild_cmd(ctx: click.Context) -> None:
    client = _get_client()
    try:
        client.rebuild_index()
    except Exception as exc:
        err(ctx.obj["json"], "ERROR", str(exc))
    ok(ctx.obj["json"], message="Index rebuilt")


def _render_human_with_console(payload: Dict[str, Any], console: Console) -> None:
    status = payload.get("status", "ok")

    if status == "error":
        title = f"Error: {payload.get('code', 'ERROR')}"
        message = payload.get("message", "")
        console.print(Panel(message, title=title, style="red"))
        return

    ctx = click.get_current_context(silent=True)
    command_path = ctx.command_path if ctx else ""
    
    # Remove the root command name (e.g., 'runnrr' or 'cli') to get the relative path
    parts = command_path.split()
    if len(parts) > 1:
        cmd_name = " ".join(parts[1:])
    else:
        cmd_name = command_path

    if cmd_name == "init":
        console.print(Panel(f"Runnrr workspace initialized at [cyan]{payload.get('path')}[/cyan]", title="Init", style="green"))
    elif cmd_name == "status":
        _render_status(console, payload)
    elif cmd_name == "migrate":
        counts = payload.get("counts", {})
        console.print(Panel(f"Migration successful!\nMigrated {counts.get('tickets')} tickets, {counts.get('epics')} epics, {counts.get('adrs')} ADRs.\nOld files archived to {payload.get('archive')}", title="Migrate", style="green"))
    elif cmd_name == "events":
        _render_events(console, payload)
    elif cmd_name == "create":
        ticket = payload.get("ticket", {})
        console.print(Panel(f"Created ticket [bold cyan]{ticket.get('id')}[/bold cyan]: {ticket.get('title')}", title="Create", style="green"))
    elif cmd_name == "epic create":
        epic = payload.get("epic", {})
        console.print(Panel(f"Created epic [bold cyan]{epic.get('id')}[/bold cyan]: {epic.get('title')}", title="Epic Create", style="green"))
    elif cmd_name == "list":
        _render_list(console, payload)
    elif cmd_name == "context":
        _render_context(console, payload)
    elif cmd_name == "search":
        _render_search_results(console, payload)
    elif cmd_name == "find-related":
        _render_search_results(console, payload)
    elif cmd_name == "link":
        console.print(Panel(f"Linked [bold cyan]{payload.get('source')}[/bold cyan] ↔ [bold cyan]{payload.get('target')}[/bold cyan]", title="Link", style="green"))
    elif cmd_name == "index rebuild":
        console.print(Panel(payload.get("message", "Index rebuilt"), title="Index", style="green"))
    elif cmd_name == "epic list":
        _render_epic_list(console, payload)
    elif cmd_name in ("start", "done", "block"):
        new = payload.get("new_state", "unknown")
        tid = payload.get("ticket_id")
        console.print(Panel(f"Ticket [bold cyan]{tid}[/bold cyan] → [green]{new}[/green]", title=cmd_name.capitalize(), style="blue"))
    elif cmd_name == "log":
        console.print(Panel(f"Logged to [bold cyan]{payload.get('ticket_id')}[/bold cyan]. Total entries: {payload.get('entry_count')}", title="Log", style="green"))
    elif cmd_name == "describe":
        _render_ticket_detail(console, payload.get("ticket", {}))
    elif cmd_name == "epic describe":
        _render_epic_detail(console, payload.get("epic", {}))
    elif cmd_name == "adr create":
        adr = payload.get("adr", {})
        console.print(Panel(f"Created ADR [bold cyan]{adr.get('id')}[/bold cyan]: {adr.get('title')}", title="ADR Create", style="green"))
    elif cmd_name == "adr list":
        _render_adr_list(console, payload)
    elif cmd_name == "adr accept":
        status = payload.get("status", "unknown")
        aid = payload.get("adr_id")
        console.print(Panel(f"ADR [bold cyan]{aid}[/bold cyan] updated to [green]{status}[/green]", title="ADR Accept", style="blue"))
    elif cmd_name == "adr describe":
        _render_adr_detail(console, payload.get("adr", {}))


def _render_status(console: Console, payload: Dict[str, Any]) -> None:  # pragma: no cover
    console.print(f"\n[bold]Runnrr Workspace Status[/bold]\n")
    
    table = Table(show_header=False, box=None)
    table.add_column("Field", style="cyan")
    table.add_column("Value")
    
    table.add_row("Project Root", payload.get("project_root"))
    
    db = payload.get("database", {})
    db_status = "[green]healthy[/green]" if db.get("healthy") else "[red]unhealthy[/red]"
    table.add_row("Database", f"{db.get('path')} ({db_status}, {db.get('size_kb')} KB)")
    table.add_row("Schema", f"version {db.get('schema_version')}")
    
    counts = payload.get("counts", {})
    t = counts.get("tickets", {})
    t_sum = f"{sum(t.values())} total ({t.get('in-progress', 0)} in-progress, {t.get('todo', 0)} todo, {t.get('blocked', 0)} blocked, {t.get('done', 0)} done)"
    table.add_row("Tickets", t_sum)
    table.add_row("Epics", str(counts.get("epics")))
    table.add_row("ADRs", str(counts.get("adrs")))
    
    git_status = "[green]✓ .runnrr/ in .gitignore[/green]" if payload.get("git_isolated") else "[yellow]⚠ .runnrr/ NOT in .gitignore[/yellow]"
    table.add_row("Host Git", git_status)
    
    console.print(table)


def _render_events(console: Console, payload: Dict[str, Any]) -> None:  # pragma: no cover
    events = payload.get("events", [])
    table = Table(title="Event Log")
    table.add_column("Date", style="dim")
    table.add_column("Type", style="cyan")
    table.add_column("Entity", style="bold")
    table.add_column("Actor")
    table.add_column("Data", style="italic")
    
    for e in events:
        table.add_row(
            str(e.get("created_at", "")[:19]),
            str(e.get("event_type", "")),
            f"{e.get('entity_type', '')}: {e.get('entity_id', '')}",
            str(e.get("actor") or "system"),
            json.dumps(e.get("data", {}))
        )
    console.print(table)


def _render_list(console: Console, payload: Dict[str, Any]) -> None:  # pragma: no cover
    tickets = payload.get("tickets", [])
    summary = payload.get("summary", {})
    showing = payload.get("showing", "actionable")
    
    console.print(f"\n[bold]Runnrr[/bold] · {len(tickets)} {showing} tickets\n")
    
    # Group tickets by status for default view
    if showing == "actionable":
        in_progress = [t for t in tickets if t['status'] == "in-progress"]
        todo = [t for t in tickets if t['status'] == "todo"]
        
        if in_progress:
            console.print("[bold yellow]IN PROGRESS[/bold yellow]")
            for t in in_progress:
                _render_ticket_row(console, t, symbol="●", color="yellow")
            console.print()
            
        if todo:
            console.print("[bold cyan]TODO (ready to start)[/bold cyan]")
            for t in todo:
                _render_ticket_row(console, t, symbol="○", color="cyan")
            console.print()
    elif showing == "blocked":
        console.print("[bold red]BLOCKED TICKETS[/bold red]")
        for t in tickets:
            _render_ticket_row(console, t, symbol="✗", color="red")
            blockers = t.get("blocked_by_detail", [])
            if blockers:
                for b in blockers:
                    console.print(f"      [dim]Blocked by: {b.get('id')} ({b.get('title')}) — {b.get('status')}[/dim]")
        console.print()
    else:
        # Just a table for other views
        table = Table(box=None, show_header=True)
        table.add_column("ID", style="dim")
        table.add_column("Title")
        table.add_column("Priority")
        table.add_column("Progress")
        
        for t in tickets:
            prog = f"{t.get('criteria_done')}/{t.get('criteria_total')} AC"
            table.add_row(t.get("id"), t.get("title"), t.get("priority"), prog)
        console.print(table)

    # Summary line
    blocked_count = summary.get("blocked", 0)
    backlog_count = summary.get("backlog", 0)
    
    if blocked_count:
        console.print(f"[red]{blocked_count} tickets blocked[/red] — run `runnrr list --blocked` to see them")
    if backlog_count:
        console.print(f"[dim]{backlog_count} tickets in backlog[/dim] — run `runnrr list --status backlog`")


def _render_ticket_row(console: Console, t: Dict[str, Any], symbol: str, color: str) -> None:
    tags = f" [dim]{', '.join(t.get('tags', []))}[/dim]" if t.get('tags') else ""
    epic = f" [blue]Epic: {t.get('epic_id')}[/blue]" if t.get('epic_id') else ""
    owner = f" · [dim]Owner: {t.get('owner')}[/dim]" if t.get('owner') else ""
    
    console.print(f"  [{color}]{symbol}[/{color}] [bold]{t.get('id')}[/bold] {t.get('title')} [{t.get('priority')}]{tags}")
    if epic or owner:
        console.print(f"    {epic}{owner}")


def _render_epic_list(console: Console, payload: Dict[str, Any]) -> None:  # pragma: no cover
    epics = payload.get("epics", [])
    table = Table(title="Epics")
    table.add_column("ID", style="cyan")
    table.add_column("Title")
    table.add_column("Priority")
    for epic in epics:
        table.add_row(
            str(epic.get("id", "")),
            str(epic.get("title", "")),
            str(epic.get("priority", "")),
        )
    console.print(table)


def _render_ticket_detail(console: Console, ticket: Dict[str, Any]) -> None:  # pragma: no cover
    table = Table(show_header=False, box=None)
    table.add_column("Field", style="cyan", no_wrap=True)
    table.add_column("Value")
    for k in ["id", "title", "status", "priority", "owner", "epic", "tags", "estimated_effort"]:
        if ticket.get(k):
            table.add_row(k.replace("_", " ").capitalize(), str(ticket[k]))
    console.print(Panel(table, title="Ticket"))

    if ticket.get("goal_text"):
        console.print(Panel(ticket["goal_text"], title="Goal"))

    tasks = ticket.get("tasks") or []
    if tasks:
        table = Table(title="Tasks")
        table.add_column("Done")
        table.add_column("Task")
        for item in tasks:
            table.add_row("x" if item.get("done") else " ", str(item.get("text", "")))
        console.print(table)

    criteria = ticket.get("acceptance_criteria") or []
    if criteria:
        table = Table(title="Acceptance Criteria")
        table.add_column("Done")
        table.add_column("Criteria")
        for item in criteria:
            table.add_row("x" if item.get("done") else " ", str(item.get("text", "")))
        console.print(table)

    log_entries = ticket.get("execution_log") or []
    if log_entries:
        table = Table(title="Log")
        table.add_column("Timestamp")
        table.add_column("Message")
        for entry in log_entries:
            table.add_row(str(entry.get("timestamp", "")), str(entry.get("message", "")))
        console.print(table)

    if ticket.get("notes_text"):
        console.print(Panel(ticket["notes_text"], title="Notes"))


def _render_epic_detail(console: Console, epic: Dict[str, Any]) -> None:  # pragma: no cover
    table = Table(show_header=False, box=None)
    table.add_column("Field", style="cyan", no_wrap=True)
    table.add_column("Value")
    for k in ["id", "title", "status", "priority", "tags"]:
        if epic.get(k):
            table.add_row(k.capitalize(), str(epic[k]))
    
    progress = epic.get("progress", {})
    table.add_row("Progress", f"{progress.get('done')}/{progress.get('total')} ({progress.get('percent')}%)")
    
    console.print(Panel(table, title="Epic"))

    if epic.get("goal_text"):
        console.print(Panel(epic["goal_text"], title="Goal"))

    metrics = epic.get("success_metrics") or []
    if metrics:
        table = Table(title="Success Metrics")
        table.add_column("Metric")
        for item in metrics:
            table.add_row(str(item))
        console.print(table)

    if epic.get("notes_text"):
        console.print(Panel(epic["notes_text"], title="Notes"))


def _render_adr_list(console: Console, payload: Dict[str, Any]) -> None:  # pragma: no cover
    adrs = payload.get("adrs", [])
    table = Table(title="ADRs")
    table.add_column("ID", style="cyan")
    table.add_column("Title")
    table.add_column("Status")
    table.add_column("Date")
    for adr in adrs:
        table.add_row(
            str(adr.get("id", "")),
            str(adr.get("title", "")),
            str(adr.get("status", "")),
            str(adr.get("date", "")),
        )
    console.print(table)


def _render_adr_detail(console: Console, adr: Dict[str, Any]) -> None:  # pragma: no cover
    table = Table(show_header=False, box=None)
    table.add_column("Field", style="cyan", no_wrap=True)
    table.add_column("Value")
    for k in ["id", "title", "status", "date", "tags", "linked_tickets", "linked_epics", "supersedes", "superseded_by"]:
        if adr.get(k):
            table.add_row(k.replace("_", " ").capitalize(), str(adr[k]))
    console.print(Panel(table, title="ADR"))

    if adr.get("context_text"):
        console.print(Panel(adr["context_text"], title="Context"))
    if adr.get("decision_text"):
        console.print(Panel(adr["decision_text"], title="Decision", style="green"))
    if adr.get("consequences_text"):
        console.print(Panel(adr["consequences_text"], title="Consequences"))
    if adr.get("alternatives_text"):
        console.print(Panel(adr["alternatives_text"], title="Alternatives"))


def _render_context(console: Console, payload: Dict[str, Any]) -> None:  # pragma: no cover
    sections = payload.get("sections", [])
    budget = payload.get("budget", 4000)
    used = payload.get("tokens_used", 0)

    console.print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    console.print(f" Context for {payload.get('ticket_id')}")
    console.print(f" {used} / {budget} tokens used")
    console.print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

    for section in sections:
        type_ = section.get("type")
        content = section.get("content")
        sid = section.get("id")

        if type_ == "ticket":
            _render_ticket_detail(console, content)
        elif type_ == "blocker":
            console.print(f"\n[red]BLOCKER: {sid}[/red]")
            _render_ticket_detail(console, content)
        elif type_ in ("direct_adr", "tag_adr"):
            console.print(f"\n[bold blue]ADR: {sid}[/bold blue]")
            _render_adr_detail(console, content)
        elif type_ == "epic":
            console.print(f"\n[bold magenta]Epic: {sid}[/bold magenta]")
            _render_epic_detail(console, content)
        elif type_ == "convention":
            console.print(Panel(content, title=f"Convention: {sid}", style="dim"))

    excluded = payload.get("excluded", [])
    if excluded:
        console.print(f"\n[yellow]Excluded (budget):[/yellow] {', '.join([e['id'] for e in excluded])}")
    
    console.print(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")


def _render_search_results(console: Console, payload: Dict[str, Any]) -> None:  # pragma: no cover
    results = payload.get("results", [])
    count = payload.get("count", 0)
    
    console.print(f"\nFound {count} results\n")
    
    table = Table(box=None, show_header=False)
    table.add_column("ID", style="cyan", width=12)
    table.add_column("Summary")
    
    for res in results:
        summary = f"[bold]{res.get('title')}[/bold] [{res.get('status')}]\n"
        summary += f"[dim]Type: {res.get('type')}  Tags: {res.get('tags')}[/dim]"
        table.add_row(res.get("id"), summary)
        table.add_row("", "") # spacer
        
    console.print(table)

