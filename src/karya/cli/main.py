"""Command-line interface for Karya."""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, List

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from karya.core.models import Priority, TicketType
from karya.core.validator import validate_ticket
from karya.exceptions import (
    IncompleteAcceptanceCriteria,
    InvalidTransitionError,
    TicketNotFoundError,
    UpdateForbiddenError,
    ValidationError,
)
from karya.sdk.client import KaryaClient


def _emit(payload: Dict[str, Any], use_json: bool) -> None:
    if use_json:
        click.echo(json.dumps(payload))
    else:
        _render_human(payload)


def ok(use_json: bool, **kwargs: Any) -> None:
    _emit({"status": "ok", **kwargs}, use_json)


def err(use_json: bool, code: str, message: str, **kwargs: Any) -> None:
    _emit({"status": "error", "code": code, "message": message, **kwargs}, use_json)
    raise SystemExit(1)


def _get_client(agent: str | None = None) -> KaryaClient:
    return KaryaClient(".", agent=agent)


@click.group(add_help_option=False, invoke_without_command=True)
@click.option("--help", "show_help", is_flag=True, help="Show help")
@click.option("--json", "use_json", is_flag=True, help="Use JSON output")
@click.pass_context
def cli(ctx: click.Context, show_help: bool, use_json: bool) -> None:
    ctx.ensure_object(dict)
    ctx.obj["json"] = use_json

    if show_help or ctx.invoked_subcommand is None:
        commands = sorted(ctx.command.commands.keys())
        ok(
            use_json,
            commands=commands,
            command_descriptions=_command_descriptions(),
            message="Karya CLI - filesystem-first execution workflow for agents.",
        )
        ctx.exit(0)


@cli.command("init")
@click.pass_context
def init_cmd(ctx: click.Context) -> None:
    client = _get_client()
    client.init()
    ok(ctx.obj["json"], path=".karya", initialized=True)


@cli.command("create")
@click.argument("title")
@click.option("--type", "type_", default="feature")
@click.option("--priority", default="medium")
@click.option("--epic", default=None)
@click.option("--agent", default=None)
@click.option("--effort", default=1, type=int)
@click.option("--label", "labels", multiple=True)
@click.option("--context", default="")
@click.pass_context
def create_cmd(
    ctx: click.Context,
    title: str,
    type_: str,
    priority: str,
    epic: str | None,
    agent: str | None,
    effort: int,
    labels: List[str],
    context: str,
) -> None:
    client = _get_client(agent)
    try:
        ticket_type = TicketType(type_.lower())
        priority_value = Priority(priority.lower())
    except ValueError as exc:
        err(ctx.obj["json"], "INVALID_OPTION", str(exc))
    try:
        ticket = client.create_ticket(
            title=title,
            context=context,
            type=ticket_type,
            priority=priority_value,
            epic=epic,
            labels=list(labels),
            estimated_effort=effort,
        )
    except ValidationError as exc:
        err(ctx.obj["json"], "VALIDATION_ERROR", str(exc))

    ok(
        ctx.obj["json"],
        ticket={
            "id": ticket.id,
            "title": ticket.title,
            "status": ticket.status.value,
            "path": str(ticket.path) if ticket.path else None,
        },
    )


@cli.command("list")
@click.option("--state", "state", default=None)
@click.option("--agent", default=None)
@click.option("--epic", default=None)
@click.option("--label", default=None)
@click.pass_context
def list_cmd(
    ctx: click.Context, state: str | None, agent: str | None, epic: str | None, label: str | None
) -> None:
    client = _get_client()
    tickets = client.list_tickets(status=state, agent=agent)

    if epic:
        tickets = [ticket for ticket in tickets if ticket.epic == epic]
    if label:
        tickets = [ticket for ticket in tickets if label in ticket.labels]

    payload = [
        {
            "id": ticket.id,
            "title": ticket.title,
            "status": ticket.status.value,
            "priority": ticket.priority.value,
            "owner": ticket.owner,
        }
        for ticket in tickets
    ]
    ok(ctx.obj["json"], count=len(payload), tickets=payload)


@cli.command("next")
@click.option("--agent", required=True)
@click.pass_context
def next_cmd(ctx: click.Context, agent: str) -> None:
    client = _get_client(agent)
    ticket = client.get_next_ticket(agent)
    if ticket is None:
        ok(ctx.obj["json"], status="empty", message="No eligible tickets.")
        return
    ok(ctx.obj["json"], ticket=client.describe_ticket(ticket.id))


@cli.command("start")
@click.argument("ticket_id")
@click.option("--agent", default=None)
@click.pass_context
def start_cmd(ctx: click.Context, ticket_id: str, agent: str | None) -> None:
    client = _get_client(agent)
    try:
        ticket = client.assign(ticket_id, agent or "") if agent else client.get_ticket(ticket_id)
        previous = ticket.status.value
        if ticket.status.value == "backlog":
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
    except InvalidTransitionError as exc:
        err(ctx.obj["json"], "INVALID_TRANSITION", str(exc))
    except TicketNotFoundError as exc:
        err(ctx.obj["json"], "NOT_FOUND", str(exc))

    ok(
        ctx.obj["json"],
        ticket_id=ticket.id,
        previous_state=None,
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
    except TicketNotFoundError as exc:
        err(ctx.obj["json"], "NOT_FOUND", str(exc))
    except InvalidTransitionError as exc:
        err(ctx.obj["json"], "INVALID_TRANSITION", str(exc))

    ok(ctx.obj["json"], ticket_id=ticket_id, new_state="blocked", reason=reason)


@cli.command("log")
@click.argument("ticket_id")
@click.argument("message")
@click.pass_context
def log_cmd(ctx: click.Context, ticket_id: str, message: str) -> None:
    client = _get_client()
    try:
        ticket = client.log(ticket_id, message)
    except TicketNotFoundError as exc:
        err(ctx.obj["json"], "NOT_FOUND", str(exc))

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
    except TicketNotFoundError as exc:
        err(ctx.obj["json"], "NOT_FOUND", str(exc))

    ok(ctx.obj["json"], ticket=description)


@cli.command("update")
@click.argument("ticket_id")
@click.option("--field", required=True)
@click.option("--value", required=True)
@click.pass_context
def update_cmd(ctx: click.Context, ticket_id: str, field: str, value: str) -> None:
    client = _get_client()
    updates = {field: _parse_value(value)}
    if field == "priority" and isinstance(updates[field], str):
        try:
            updates[field] = Priority(updates[field].lower())
        except ValueError as exc:
            err(ctx.obj["json"], "INVALID_OPTION", str(exc))
    try:
        client.update_ticket(ticket_id, updates)
    except UpdateForbiddenError as exc:
        err(ctx.obj["json"], "UPDATE_FORBIDDEN", str(exc))
    except ValidationError as exc:
        err(ctx.obj["json"], "VALIDATION_ERROR", str(exc))
    except TicketNotFoundError as exc:
        err(ctx.obj["json"], "NOT_FOUND", str(exc))

    ok(ctx.obj["json"], ticket_id=ticket_id, updated=updates)


@cli.command("assign")
@click.argument("ticket_id")
@click.option("--agent", required=True)
@click.pass_context
def assign_cmd(ctx: click.Context, ticket_id: str, agent: str) -> None:
    client = _get_client()
    try:
        client.assign(ticket_id, agent)
    except TicketNotFoundError as exc:
        err(ctx.obj["json"], "NOT_FOUND", str(exc))

    ok(ctx.obj["json"], ticket_id=ticket_id, assigned_to=agent)


@cli.command("exec")
@click.option("--agent", required=True)
@click.pass_context
def exec_cmd(ctx: click.Context, agent: str) -> None:
    client = _get_client(agent)
    ticket = client.get_next_ticket(agent)
    if ticket is None:
        ok(ctx.obj["json"], status="empty", message="No eligible tickets.")
        return

    description = client.describe_ticket(ticket.id)
    ok(
        ctx.obj["json"],
        ticket=description,
        context=client.load_context(),
        instructions=ticket.agent_instructions,
    )


@cli.group("sprint")
@click.pass_context
def sprint_cmd(ctx: click.Context) -> None:
    return None


@sprint_cmd.command("plan")
@click.option("--limit", default=5, type=int)
@click.pass_context
def sprint_plan_cmd(ctx: click.Context, limit: int) -> None:
    client = _get_client()
    sprint = client.plan_sprint(limit=limit)
    ok(ctx.obj["json"], sprint=sprint.model_dump(mode="json"))


@sprint_cmd.command("status")
@click.pass_context
def sprint_status_cmd(ctx: click.Context) -> None:
    client = _get_client()
    try:
        status = client._sprints.status()
    except Exception as exc:
        err(ctx.obj["json"], "SPRINT_NOT_FOUND", str(exc))

    ok(
        ctx.obj["json"],
        sprint=status["sprint"].model_dump(mode="json"),
        breakdown=status["breakdown"],
    )


@sprint_cmd.command("close")
@click.pass_context
def sprint_close_cmd(ctx: click.Context, ticket_id: str) -> None:
    client = _get_client()
    try:
        sprint = client._sprints.close()
    except Exception as exc:
        err(ctx.obj["json"], "SPRINT_NOT_FOUND", str(exc))

    ok(
        ctx.obj["json"],
        sprint_id=sprint.id,
        completed=sprint.completed_points,
        incomplete=len(sprint.tickets) - sprint.completed_points,
    )


@cli.command("events")
@click.option("--ticket", "ticket_id", default=None)
@click.option("--last", default=20, type=int)
@click.pass_context
def events_cmd(ctx: click.Context, ticket_id: str | None, last: int) -> None:
    client = _get_client()
    events = client.get_events(ticket_id=ticket_id, last=last)
    ok(ctx.obj["json"], events=[event.model_dump(mode="json") for event in events])


@cli.command("validate")
@click.pass_context
def validate_cmd(ctx: click.Context) -> None:
    client = _get_client()
    tickets = client.list_tickets()
    invalid: list[dict] = []
    for ticket in tickets:
        errors = validate_ticket(ticket)
        if errors:
            invalid.append({"ticket_id": ticket.id, "errors": errors})

    ok(
        ctx.obj["json"],
        valid=len(tickets) - len(invalid),
        invalid=len(invalid),
        errors=invalid,
    )


def _parse_value(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


from rich.markdown import Markdown


def _render_human(payload: Dict[str, Any]) -> None:
    console = Console()
    status = payload.get("status", "ok")

    if status == "error":
        title = f"Error: {payload.get('code', 'ERROR')}"
        message = payload.get("message", "")
        console.print(Panel(message, title=title, style="red"))
        if "unchecked" in payload:
            table = Table(title="Unchecked Acceptance Criteria")
            table.add_column("Criteria")
            for item in payload["unchecked"]:
                table.add_row(str(item))
            console.print(table)
        return

    if "commands" in payload:
        _render_help(console, payload)
        return

    if status == "empty":
        console.print(Panel(payload.get("message", "No results."), title="Empty"))
        return

    ctx = click.get_current_context(silent=True)
    command_path = ctx.command_path if ctx else ""
    cmd_name = command_path.replace("karya ", "").strip()

    if cmd_name == "init":
        console.print(Panel(f"Karya workspace initialized at [cyan]{payload.get('path')}[/cyan]", title="Init", style="green"))
    elif cmd_name == "create":
        ticket = payload.get("ticket", {})
        console.print(Panel(f"Created ticket [bold cyan]{ticket.get('id')}[/bold cyan]: {ticket.get('title')}", title="Create", style="green"))
    elif cmd_name == "list":
        _render_list(console, payload)
    elif cmd_name == "next":
        _render_ticket_detail(console, payload.get("ticket", {}))
    elif cmd_name in ("start", "done", "block"):
        prev = payload.get("previous_state", "unknown")
        new = payload.get("new_state", "unknown")
        tid = payload.get("ticket_id")
        reason = f"\nReason: {payload.get('reason')}" if payload.get("reason") else ""
        console.print(Panel(f"Ticket [bold cyan]{tid}[/bold cyan]: [yellow]{prev}[/yellow] → [green]{new}[/green]{reason}", title=cmd_name.capitalize(), style="blue"))
    elif cmd_name == "log":
        console.print(Panel(f"Logged to [bold cyan]{payload.get('ticket_id')}[/bold cyan]. Total entries: {payload.get('entry_count')}", title="Log", style="green"))
    elif cmd_name == "describe":
        _render_ticket_detail(console, payload.get("ticket", {}))
    elif cmd_name == "update":
        updates = payload.get("updated", {})
        table = Table(title=f"Updated Ticket {payload.get('ticket_id')}")
        table.add_column("Field", style="cyan")
        table.add_column("New Value")
        for k, v in updates.items():
            table.add_row(str(k), str(v))
        console.print(table)
    elif cmd_name == "assign":
        console.print(Panel(f"Ticket [bold cyan]{payload.get('ticket_id')}[/bold cyan] assigned to [yellow]{payload.get('assigned_to')}[/yellow]", title="Assign", style="green"))
    elif cmd_name == "exec":
        _render_exec(console, payload)
    elif cmd_name == "sprint plan":
        sprint = payload.get("sprint", {})
        console.print(Panel(f"Sprint [bold cyan]{sprint.get('id')}[/bold cyan] planned with {len(sprint.get('tickets', []))} tickets.", title="Sprint Planned", style="green"))
        _render_list(console, {"tickets": [{"id": tid, "title": "...", "status": "todo", "priority": "...", "owner": None} for tid in sprint.get("tickets", [])]})
    elif cmd_name == "sprint status":
        _render_sprint_status(console, payload)
    elif cmd_name == "sprint close":
        console.print(Panel(f"Sprint [bold cyan]{payload.get('sprint_id')}[/bold cyan] closed.\n[green]Completed: {payload.get('completed')}[/green]\n[red]Incomplete: {payload.get('incomplete')}[/red]", title="Sprint Closed"))
    elif cmd_name == "events":
        _render_events(console, payload)
    elif cmd_name == "validate":
        _render_validate(console, payload)
    else:
        console.print(_dict_panel(payload, title="Result"))


def _render_help(console: Console, payload: Dict[str, Any]) -> None:
    message = payload.get("message")
    if message:
        console.print(Panel(message, title="Karya"))
    descriptions = payload.get("command_descriptions", {})
    table = Table(title="Commands")
    table.add_column("Command", style="cyan")
    table.add_column("Description")
    for command in payload["commands"]:
        table.add_row(str(command), str(descriptions.get(command, "")))
    console.print(table)


def _render_list(console: Console, payload: Dict[str, Any]) -> None:
    tickets = payload.get("tickets", [])
    table = Table(title="Tickets")
    table.add_column("ID", style="cyan")
    table.add_column("Title")
    table.add_column("Status")
    table.add_column("Priority")
    table.add_column("Owner")
    for ticket in tickets:
        table.add_row(
            str(ticket.get("id", "")),
            str(ticket.get("title", "")),
            str(ticket.get("status", "")),
            str(ticket.get("priority", "")),
            str(ticket.get("owner") or ""),
        )
    console.print(table)


def _render_events(console: Console, payload: Dict[str, Any]) -> None:
    table = Table(title="Events")
    table.add_column("Timestamp")
    table.add_column("Event")
    table.add_column("Ticket")
    table.add_column("Actor")
    for event in payload.get("events", []):
        table.add_row(
            str(event.get("timestamp", "")),
            str(event.get("event", "")),
            str(event.get("ticket_id", "")),
            str(event.get("actor", "")),
        )
    console.print(table)


def _render_validate(console: Console, payload: Dict[str, Any]) -> None:
    console.print(
        Panel(
            Text(
                f"Valid: {payload.get('valid', 0)} | Invalid: {payload.get('invalid', 0)}",
                style="bold",
            ),
            title="Validation Summary",
        )
    )
    errors = payload.get("errors", [])
    if errors:
        table = Table(title="Validation Errors", style="red")
        table.add_column("Ticket")
        table.add_column("Errors")
        for entry in errors:
            table.add_row(str(entry.get("ticket_id")), "; ".join(entry.get("errors", [])))
        console.print(table)


def _render_sprint_status(console: Console, payload: Dict[str, Any]) -> None:
    sprint = payload.get("sprint", {})
    console.print(_dict_panel(sprint, title="Sprint"))
    breakdown = payload.get("breakdown", {})
    table = Table(title="Breakdown")
    table.add_column("State")
    table.add_column("Count")
    for key, value in breakdown.items():
        table.add_row(str(key), str(value))
    console.print(table)


def _render_exec(console: Console, payload: Dict[str, Any]) -> None:
    ticket = payload.get("ticket", {})
    _render_ticket_detail(console, ticket)

    context = payload.get("context")
    if context:
        console.print(Panel(Markdown(context), title="Context"))

    instructions = payload.get("instructions")
    if instructions:
        console.print(Panel(instructions, title="Agent Instructions", style="yellow"))


def _dict_panel(data: Dict[str, Any], title: str) -> Panel:
    table = Table(show_header=False, box=None)
    table.add_column("Field", style="cyan", no_wrap=True)
    table.add_column("Value")
    for key, value in data.items():
        table.add_row(str(key), str(value))
    return Panel(table, title=title)


def _render_ticket_detail(console: Console, ticket: Dict[str, Any]) -> None:
    header_fields = {
        "id": ticket.get("id"),
        "title": ticket.get("title"),
        "status": ticket.get("status"),
        "priority": ticket.get("priority"),
        "owner": ticket.get("owner"),
    }
    console.print(_dict_panel({k: v for k, v in header_fields.items() if v}, title="Ticket"))

    if ticket.get("context_text"):
        console.print(Panel(ticket["context_text"], title="Context"))
    if ticket.get("goal_text"):
        console.print(Panel(ticket["goal_text"], title="Goal"))
    if ticket.get("scope_text"):
        console.print(Panel(ticket["scope_text"], title="Scope"))

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
        table = Table(title="Execution Log")
        table.add_column("Timestamp")
        table.add_column("Message")
        for entry in log_entries:
            table.add_row(str(entry.get("timestamp", "")), str(entry.get("message", "")))
        console.print(table)

    if ticket.get("agent_instructions"):
        console.print(Panel(ticket["agent_instructions"], title="Agent Instructions"))


def _command_descriptions() -> Dict[str, str]:
    return {
        "assign": "Assign a ticket to an agent.",
        "block": "Move a ticket to blocked and log the reason.",
        "create": "Create a new ticket in the backlog.",
        "describe": "Show full ticket details.",
        "done": "Complete a ticket after acceptance criteria are met.",
        "events": "List recent events (optionally filtered by ticket).",
        "exec": "Get next ticket plus context for an agent.",
        "init": "Initialize the .karya workspace.",
        "list": "List tickets with optional filters.",
        "log": "Append an execution log entry to a ticket.",
        "next": "Get the next eligible ticket for an agent.",
        "sprint": "Plan, view, and close sprints.",
        "start": "Assign and move a ticket into progress.",
        "update": "Update allowed ticket fields.",
        "validate": "Validate all tickets against schema.",
    }
