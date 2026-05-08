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


def _get_client(agent: str | None = None) -> RunnrrClient:
    return RunnrrClient(".", agent=agent)


@click.group(add_help_option=False, invoke_without_command=True)
@click.option("--help", "show_help", is_flag=True, help="Show help")
@click.option("--json", "use_json", is_flag=True, help="Use JSON output")
@click.pass_context
def cli(ctx: click.Context, show_help: bool, use_json: bool) -> None:
    ctx.ensure_object(dict)
    ctx.obj["json"] = use_json

    if show_help or ctx.invoked_subcommand is None:  # pragma: no cover
        console = Console(force_terminal=True, width=100)
        console.print(Panel("Runnrr - filesystem-native agent workspace protocol", title="Runnrr"))
        console.print("\n[bold]The Five Commands That Matter:[/bold]")
        console.print("  runnrr next        # what should I work on? (Phase B)")
        console.print("  runnrr context     # what do I need to know? (Phase B)")
        console.print("  runnrr log         # what did I just do?")
        console.print("  runnrr done        # I finished this")
        console.print("  runnrr adr         # I made an architectural decision")
        ctx.exit(0)


@cli.command("init")
@click.pass_context
def init_cmd(ctx: click.Context) -> None:
    client = _get_client()
    client.init()
    ok(ctx.obj["json"], path=".runnrr", initialized=True)


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
@click.option("--status", default=None)
@click.option("--epic", default=None)
@click.option("--tag", default=None)
@click.pass_context
def list_cmd(
    ctx: click.Context, status: str | None, epic: str | None, tag: str | None
) -> None:
    client = _get_client()
    tickets = client.list_tickets(status=status, epic=epic, tag=tag)

    payload = [
        {
            "id": ticket.id,
            "title": ticket.title,
            "status": ticket.status.value,
            "priority": ticket.priority.value,
        }
        for ticket in tickets
    ]
    ok(ctx.obj["json"], count=len(payload), tickets=payload)


@cli.command("next")
@click.option("--epic", default=None)
@click.option("--tag", default=None)
@click.pass_context
def next_cmd(
    ctx: click.Context, epic: str | None, tag: str | None
) -> None:
    client = _get_client()
    ticket = client.get_next_ticket(tag=tag, epic=epic)
    if not ticket:
        err(ctx.obj["json"], "NOT_FOUND", "No executable tickets found.")
        
    ok(
        ctx.obj["json"],
        ticket={
            "id": ticket.id,
            "title": ticket.title,
            "priority": ticket.priority.value,
            "estimated_effort": ticket.estimated_effort,
            "epic": ticket.epic,
            "tags": ticket.tags,
            "status": ticket.status.value,
        },
    )


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
    linked_tickets: List[str],
    linked_epics: List[str],
    tags: List[str],
) -> None:
    client = _get_client()
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

    ok(
        ctx.obj["json"],
        adr={
            "id": adr.id,
            "title": adr.title,
            "status": adr.status.value,
        },
    )


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


@cli.command("exec")
@click.argument("ticket_id", required=False)
@click.option("--agent", default=None)
@click.pass_context
def exec_cmd(ctx: click.Context, ticket_id: str | None, agent: str | None) -> None:
    client = _get_client(agent)
    try:
        payload = client.execute(ticket_id)
    except Exception as exc:
        err(ctx.obj["json"], "ERROR", str(exc))
    ok(ctx.obj["json"], **payload)


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
    elif cmd_name == "create":
        ticket = payload.get("ticket", {})
        console.print(Panel(f"Created ticket [bold cyan]{ticket.get('id')}[/bold cyan]: {ticket.get('title')}", title="Create", style="green"))
    elif cmd_name == "epic create":
        epic = payload.get("epic", {})
        console.print(Panel(f"Created epic [bold cyan]{epic.get('id')}[/bold cyan]: {epic.get('title')}", title="Epic Create", style="green"))
    elif cmd_name == "list":
        _render_list(console, payload)
    elif cmd_name == "next":
        _render_next(console, payload.get("ticket", {}))
    elif cmd_name == "context":
        _render_context(console, payload)
    elif cmd_name == "exec":
        _render_exec(console, payload)
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


def _render_list(console: Console, payload: Dict[str, Any]) -> None:  # pragma: no cover
    tickets = payload.get("tickets", [])
    table = Table(title="Tickets")
    table.add_column("ID", style="cyan")
    table.add_column("Title")
    table.add_column("Status")
    table.add_column("Priority")
    for ticket in tickets:
        table.add_row(
            str(ticket.get("id", "")),
            str(ticket.get("title", "")),
            str(ticket.get("status", "")),
            str(ticket.get("priority", "")),
        )
    console.print(table)


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


def _render_next(console: Console, ticket: Dict[str, Any]) -> None:  # pragma: no cover
    if not ticket:
        console.print("[yellow]No executable tickets found.[/yellow]")
        return

    table = Table(show_header=False, box=None)
    table.add_column("Field", style="cyan", no_wrap=True)
    table.add_column("Value")
    
    table.add_row("ID", str(ticket.get("id")))
    table.add_row("Title", str(ticket.get("title")))
    table.add_row("Priority", str(ticket.get("priority")))
    table.add_row("Effort", str(ticket.get("estimated_effort")))
    table.add_row("Epic", str(ticket.get("epic") or "None"))
    table.add_row("Tags", ", ".join(ticket.get("tags", [])))
    table.add_row("Status", str(ticket.get("status")))

    console.print(Panel(table, title="Next Ticket", style="green"))


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


def _render_exec(console: Console, payload: Dict[str, Any]) -> None:  # pragma: no cover
    ticket = payload.get("ticket", {})
    console.print(Panel(f"Targeting [bold cyan]{ticket.get('id')}[/bold cyan]: {ticket.get('title')}", title="Agent Executive Interface", style="bold blue"))
    
    # Render context summary
    context = payload.get("context", {})
    console.print(f"\n[bold]Context Overview:[/bold] {context.get('tokens_used')} tokens, {len(context.get('sections', []))} sections.")
    
    # Valid actions
    actions = payload.get("valid_actions", [])
    table = Table(title="Valid Actions", box=None)
    table.add_column("Action", style="cyan")
    table.add_column("Available", justify="center")
    table.add_column("Command")
    
    for a in actions:
        avail = "[green]Yes[/green]" if a.get("available") else "[red]No[/red]"
        table.add_row(a.get("action"), avail, a.get("command"))
    console.print(table)
    
    suggested = payload.get("suggested_command")
    if suggested:
        console.print(Panel(f"Suggested Command: [bold green]{suggested}[/bold bold green]", border_style="bright_blue"))


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

