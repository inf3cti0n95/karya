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

from karya.core.models import EpicStatus, EpicType, Priority, TicketType
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
    context = client.load_context_for_ticket(ticket.id)
    
    relevant_adrs = []
    if ticket.labels:
        adrs = client.list_adrs(status="accepted")
        for adr in adrs:
            if set(ticket.labels).intersection(set(adr.tags)):
                relevant_adrs.append(adr.id)

    epic_info = None
    if ticket.epic:
        try:
            epic = client.get_epic(ticket.epic)
            epic_info = {"id": epic.id, "title": epic.title, "progress": epic.progress}
        except Exception:
            pass

    ok(
        ctx.obj["json"],
        ticket=description,
        context=context,
        relevant_adrs=relevant_adrs,
        epic=epic_info,
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


@cli.group("epic")
@click.pass_context
def epic_cmd(ctx: click.Context) -> None:
    return None


@epic_cmd.command("create")
@click.argument("title")
@click.option("--type", "type_", default="feature")
@click.option("--priority", default="medium")
@click.option("--goal", default="")
@click.option("--parent", "parent_epic", default=None)
@click.option("--tag", "tags", multiple=True)
@click.option("--owner", default=None)
@click.option("--agent", default=None)
@click.pass_context
def epic_create_cmd(
    ctx: click.Context,
    title: str,
    type_: str,
    priority: str,
    goal: str,
    parent_epic: str | None,
    tags: List[str],
    owner: str | None,
    agent: str | None,
) -> None:
    client = _get_client(agent)
    try:
        epic_type = EpicType(type_.lower())
        priority_value = Priority(priority.lower())
    except ValueError as exc:
        err(ctx.obj["json"], "INVALID_OPTION", str(exc))

    epic = client.create_epic(
        title=title,
        type=epic_type,
        priority=priority_value,
        goal=goal,
        parent_epic=parent_epic,
        tags=list(tags),
        owner=owner,
    )

    ok(
        ctx.obj["json"],
        epic={
            "id": epic.id,
            "title": epic.title,
            "status": epic.status.value if epic.status else None,
            "path": str(epic.path) if epic.path else None,
        },
    )


@epic_cmd.command("list")
@click.option("--status", default=None)
@click.option("--tag", default=None)
@click.option("--parent", default=None)
@click.pass_context
def epic_list_cmd(
    ctx: click.Context,
    status: str | None,
    tag: str | None,
    parent: str | None,
) -> None:
    client = _get_client()
    status_value = EpicStatus(status) if status else None
    epics = client._epics.list(status=status_value, tag=tag, parent=parent)

    payload = [
        {
            "id": epic.id,
            "title": epic.title,
            "status": epic.status.value if epic.status else None,
            "priority": epic.priority.value,
            "owner": epic.owner,
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
@click.option("--field", required=True)
@click.option("--value", required=True)
@click.pass_context
def epic_update_cmd(ctx: click.Context, epic_id: str, field: str, value: str) -> None:
    client = _get_client()
    updates = {field: _parse_value(value)}
    try:
        epic = client.update_epic(epic_id, updates)
    except Exception as exc:
        err(ctx.obj["json"], "UPDATE_FAILED", str(exc))

    ok(ctx.obj["json"], epic=epic.model_dump(mode="json"))


@epic_cmd.command("link-ticket")
@click.argument("epic_id")
@click.argument("ticket_id")
@click.pass_context
def epic_link_ticket_cmd(ctx: click.Context, epic_id: str, ticket_id: str) -> None:
    client = _get_client()
    try:
        epic = client._epics.link_ticket(epic_id, ticket_id)
    except Exception as exc:
        err(ctx.obj["json"], "LINK_FAILED", str(exc))

    ok(ctx.obj["json"], epic=epic.model_dump(mode="json"))


@epic_cmd.command("archive")
@click.argument("epic_id")
@click.argument("reason")
@click.pass_context
def epic_archive_cmd(ctx: click.Context, epic_id: str, reason: str) -> None:
    client = _get_client()
    try:
        epic = client.archive_epic(epic_id, reason)
    except Exception as exc:
        err(ctx.obj["json"], "ARCHIVE_FAILED", str(exc))

    ok(ctx.obj["json"], epic=epic.model_dump(mode="json"))


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
@click.option("--decider", "deciders", multiple=True)
@click.option("--ticket", "linked_tickets", multiple=True)
@click.option("--epic", "linked_epics", multiple=True)
@click.option("--tag", "tags", multiple=True)
@click.option("--agent", default=None)
@click.pass_context
def adr_create_cmd(
    ctx: click.Context,
    title: str,
    context: str,
    decision: str,
    consequences: str,
    alternatives: str,
    deciders: List[str],
    linked_tickets: List[str],
    linked_epics: List[str],
    tags: List[str],
    agent: str | None,
) -> None:
    client = _get_client(agent)
    adr = client.create_adr(
        title=title,
        context=context,
        decision=decision,
        consequences=consequences,
        alternatives=alternatives,
        deciders=list(deciders),
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
            "path": str(adr.path) if adr.path else None,
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


@adr_cmd.command("supersede")
@click.argument("adr_id")
@click.argument("new_title")
@click.option("--context", required=True)
@click.option("--decision", required=True)
@click.pass_context
def adr_supersede_cmd(
    ctx: click.Context, adr_id: str, new_title: str, context: str, decision: str
) -> None:
    client = _get_client()
    try:
        new_adr = client.supersede_adr(adr_id, new_title, context, decision)
    except Exception as exc:
        err(ctx.obj["json"], "SUPERSEDE_FAILED", str(exc))

    ok(ctx.obj["json"], old_id=adr_id, new_id=new_adr.id)


@adr_cmd.command("deprecate")
@click.argument("adr_id")
@click.argument("reason")
@click.pass_context
def adr_deprecate_cmd(ctx: click.Context, adr_id: str, reason: str) -> None:
    client = _get_client()
    try:
        adr = client.deprecate_adr(adr_id, reason)
    except Exception as exc:
        err(ctx.obj["json"], "DEPRECATE_FAILED", str(exc))

    ok(ctx.obj["json"], adr_id=adr_id, status=adr.status.value, reason=reason)


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


@adr_cmd.command("link-ticket")
@click.argument("adr_id")
@click.argument("ticket_id")
@click.pass_context
def adr_link_ticket_cmd(ctx: click.Context, adr_id: str, ticket_id: str) -> None:
    client = _get_client()
    try:
        client.link_adr_ticket(adr_id, ticket_id)
    except Exception as exc:
        err(ctx.obj["json"], "LINK_FAILED", str(exc))

    ok(ctx.obj["json"], adr_id=adr_id, ticket_id=ticket_id)


@adr_cmd.command("link-epic")
@click.argument("adr_id")
@click.argument("epic_id")
@click.pass_context
def adr_link_epic_cmd(ctx: click.Context, adr_id: str, epic_id: str) -> None:
    client = _get_client()
    try:
        client.link_adr_epic(adr_id, epic_id)
    except Exception as exc:
        err(ctx.obj["json"], "LINK_FAILED", str(exc))

    ok(ctx.obj["json"], adr_id=adr_id, epic_id=epic_id)


@cli.command("search")
@click.argument("query")
@click.option("--type", "entity_type", default=None)
@click.option("--tag", "tags", multiple=True)
@click.option("--status", default=None)
@click.option("--since", default=None)
@click.option("--limit", default=10, type=int)
@click.pass_context
def search_cmd(
    ctx: click.Context,
    query: str,
    entity_type: str | None,
    tags: List[str],
    status: str | None,
    since: str | None,
    limit: int,
) -> None:
    client = _get_client()
    from datetime import date

    since_date = date.fromisoformat(since) if since else None
    results = client.search(
        query=query,
        entity_type=entity_type,
        tags=list(tags),
        status=status,
        since=since_date,
        limit=limit,
    )

    ok(ctx.obj["json"], **results.model_dump(mode="json"))


@cli.command("find-related")
@click.argument("entity_id")
@click.option("--limit", default=5, type=int)
@click.pass_context
def find_related_cmd(ctx: click.Context, entity_id: str, limit: int) -> None:
    client = _get_client()
    results = client.find_related(entity_id, limit=limit)
    ok(ctx.obj["json"], **results.model_dump(mode="json"))


@cli.command("tags")
@click.option("--entity", "entity_id", default=None)
@click.pass_context
def tags_cmd(ctx: click.Context, entity_id: str | None) -> None:
    client = _get_client()
    tags = client.get_tags(entity_id)
    ok(ctx.obj["json"], tags=tags)


@cli.group("index")
@click.pass_context
def index_cmd(ctx: click.Context) -> None:
    return None


@index_cmd.command("rebuild")
@click.pass_context
def index_rebuild_cmd(ctx: click.Context) -> None:
    client = _get_client()
    stats = client.rebuild_index()
    ok(ctx.obj["json"], **stats)


@cli.command("link")
@click.argument("source_type")
@click.argument("source_id")
@click.argument("target_type")
@click.argument("target_id")
@click.pass_context
def link_cmd(
    ctx: click.Context, source_type: str, source_id: str, target_type: str, target_id: str
) -> None:
    client = _get_client()
    try:
        client.link(source_type, source_id, target_type, target_id)
    except Exception as exc:
        err(ctx.obj["json"], "LINK_FAILED", str(exc))

    ok(
        ctx.obj["json"],
        source_type=source_type,
        source_id=source_id,
        target_type=target_type,
        target_id=target_id,
    )


@cli.command("links")
@click.argument("entity_id")
@click.pass_context
def links_cmd(ctx: click.Context, entity_id: str) -> None:
    client = _get_client()
    try:
        links = client.get_links(entity_id)
    except Exception as exc:
        err(ctx.obj["json"], "NOT_FOUND", str(exc))

    ok(ctx.obj["json"], entity=entity_id, links=links)


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
    elif cmd_name == "epic create":
        epic = payload.get("epic", {})
        console.print(Panel(f"Created epic [bold cyan]{epic.get('id')}[/bold cyan]: {epic.get('title')}", title="Epic Create", style="green"))
    elif cmd_name == "list":
        _render_list(console, payload)
    elif cmd_name == "epic list":
        _render_epic_list(console, payload)
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
    elif cmd_name == "epic describe":
        _render_epic_detail(console, payload.get("epic", {}))
    elif cmd_name == "update":
        updates = payload.get("updated", {})
        table = Table(title=f"Updated Ticket {payload.get('ticket_id')}")
        table.add_column("Field", style="cyan")
        table.add_column("New Value")
        for k, v in updates.items():
            table.add_row(str(k), str(v))
        console.print(table)
    elif cmd_name == "epic update":
        _render_epic_detail(console, payload.get("epic", {}))
    elif cmd_name == "adr create":
        adr = payload.get("adr", {})
        console.print(Panel(f"Created ADR [bold cyan]{adr.get('id')}[/bold cyan]: {adr.get('title')}", title="ADR Create", style="green"))
    elif cmd_name == "adr list":
        _render_adr_list(console, payload)
    elif cmd_name in ("adr accept", "adr supersede", "adr deprecate"):
        status = payload.get("status", "unknown")
        aid = payload.get("adr_id") or payload.get("new_id")
        console.print(Panel(f"ADR [bold cyan]{aid}[/bold cyan] updated to [green]{status}[/green]", title=cmd_name.replace("adr ", "").capitalize(), style="blue"))
    elif cmd_name == "adr describe":
        _render_adr_detail(console, payload.get("adr", {}))
    elif cmd_name == "search":
        _render_search_results(console, payload)
    elif cmd_name == "find-related":
        _render_search_results(console, payload, title="Related Entities")
    elif cmd_name == "tags":
        _render_tags(console, payload.get("tags", {}))
    elif cmd_name == "index rebuild":
        console.print(Panel(f"Index rebuilt. Indexed: [bold cyan]{payload.get('indexed')}[/bold cyan] | Tags: [bold cyan]{payload.get('tags')}[/bold cyan]", title="Index Rebuild", style="green"))
    elif cmd_name == "adr link-ticket":
        console.print(Panel(f"Linked ADR [bold cyan]{payload.get('adr_id')}[/bold cyan] to ticket [bold cyan]{payload.get('ticket_id')}[/bold cyan]", title="ADR Link", style="green"))
    elif cmd_name == "adr link-epic":
        console.print(Panel(f"Linked ADR [bold cyan]{payload.get('adr_id')}[/bold cyan] to epic [bold cyan]{payload.get('epic_id')}[/bold cyan]", title="ADR Link", style="green"))
    elif cmd_name == "link":
        console.print(Panel(f"Linked {payload.get('source_type')} [bold cyan]{payload.get('source_id')}[/bold cyan] to {payload.get('target_type')} [bold cyan]{payload.get('target_id')}[/bold cyan]", title="Link", style="green"))
    elif cmd_name == "links":
        _render_links(console, payload)
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


def _render_epic_list(console: Console, payload: Dict[str, Any]) -> None:
    epics = payload.get("epics", [])
    table = Table(title="Epics")
    table.add_column("ID", style="cyan")
    table.add_column("Title")
    table.add_column("Status")
    table.add_column("Priority")
    table.add_column("Owner")
    for epic in epics:
        table.add_row(
            str(epic.get("id", "")),
            str(epic.get("title", "")),
            str(epic.get("status", "")),
            str(epic.get("priority", "")),
            str(epic.get("owner") or ""),
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


def _render_epic_detail(console: Console, epic: Dict[str, Any]) -> None:
    header_fields = {
        "id": epic.get("id"),
        "title": epic.get("title"),
        "status": epic.get("status"),
        "priority": epic.get("priority"),
        "owner": epic.get("owner"),
    }
    console.print(_dict_panel({k: v for k, v in header_fields.items() if v}, title="Epic"))

    if epic.get("goal_text"):
        console.print(Panel(epic["goal_text"], title="Goal"))
    if epic.get("context_text"):
        console.print(Panel(epic["context_text"], title="Context"))

    metrics = epic.get("success_metrics") or []
    if metrics:
        table = Table(title="Success Metrics")
        table.add_column("Metric")
        for item in metrics:
            table.add_row(str(item))
        console.print(table)

    tickets = epic.get("tickets_detail") or []
    if tickets:
        table = Table(title="Tickets")
        table.add_column("Ticket")
        table.add_column("Status")
        for entry in tickets:
            table.add_row(str(entry.get("id", "")), str(entry.get("status", "")))
        console.print(table)


def _render_adr_list(console: Console, payload: Dict[str, Any]) -> None:
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


def _render_adr_detail(console: Console, adr: Dict[str, Any]) -> None:
    header_fields = {
        "id": adr.get("id"),
        "title": adr.get("title"),
        "status": adr.get("status"),
        "date": adr.get("date"),
    }
    console.print(_dict_panel({k: v for k, v in header_fields.items() if v}, title="ADR"))

    if adr.get("context_text"):
        console.print(Panel(adr["context_text"], title="Context"))
    if adr.get("decision_text"):
        console.print(Panel(adr["decision_text"], title="Decision", style="green"))
    if adr.get("consequences_text"):
        console.print(Panel(adr["consequences_text"], title="Consequences"))
    if adr.get("alternatives_text"):
        console.print(Panel(adr["alternatives_text"], title="Alternatives Considered"))

    links = {
        "tickets": adr.get("linked_tickets", []),
        "epics": adr.get("linked_epics", []),
        "tags": adr.get("tags", []),
        "supersedes": adr.get("supersedes"),
        "superseded_by": adr.get("superseded_by"),
    }
    console.print(_dict_panel({k: v for k, v in links.items() if v}, title="Links & Tags"))


def _render_search_results(console: Console, payload: Dict[str, Any], title: str = "Search Results") -> None:
    results = payload.get("results", [])
    if not results:
        console.print(Panel("No results found.", title=title))
        return

    table = Table(title=f"{title} ({payload.get('total', 0)})")
    table.add_column("Type", style="dim")
    table.add_column("ID", style="cyan")
    table.add_column("Title")
    table.add_column("Excerpt")
    table.add_column("Score", justify="right")

    for item in results:
        table.add_row(
            item.get("entity_type", ""),
            item.get("id", ""),
            item.get("title", ""),
            Markdown(item.get("excerpt", "")),
            f"{item.get('score', 0):.2f}"
        )
    console.print(table)


def _render_tags(console: Console, tags: Dict[str, Any]) -> None:
    if not tags:
        console.print(Panel("No tags found.", title="Tags"))
        return

    table = Table(title="Tags")
    table.add_column("Tag", style="cyan")
    table.add_column("Count/Value", justify="right")

    for tag, value in tags.items():
        table.add_row(tag, str(value))
    console.print(table)


def _render_links(console: Console, payload: Dict[str, Any]) -> None:
    entity_id = payload.get("entity", "")
    links = payload.get("links", {})
    console.print(Panel(f"Links for [bold cyan]{entity_id}[/bold cyan]", style="blue"))

    for category, items in links.items():
        if not items:
            continue
        
        if isinstance(items, list):
            table = Table(title=category.capitalize())
            if items and isinstance(items[0], dict):
                table.add_column("ID", style="cyan")
                table.add_column("Title")
                table.add_column("Status")
                for item in items:
                    table.add_row(str(item.get("id")), str(item.get("title")), str(item.get("status")))
            else:
                table.add_column("Value")
                for item in items:
                    table.add_row(str(item))
            console.print(table)
        else:
            console.print(f"[bold]{category.capitalize()}:[/bold] {items}")


def _command_descriptions() -> Dict[str, str]:
    return {
        "assign": "Assign a ticket to an agent.",
        "block": "Move a ticket to blocked and log the reason.",
        "create": "Create a new ticket in the backlog.",
        "describe": "Show full ticket details.",
        "done": "Complete a ticket after acceptance criteria are met.",
        "events": "List recent events (optionally filtered by ticket).",
        "exec": "Get next ticket plus context for an agent.",
        "epic": "Manage epics (create, list, describe, update).",
        "adr": "Manage Architecture Decision Records (create, accept, supersede, deprecate).",
        "init": "Initialize the .karya workspace.",
        "list": "List tickets with optional filters.",
        "link": "Create a bidirectional link between two entities.",
        "links": "Show all links for a given entity.",
        "log": "Append an execution log entry to a ticket.",
        "next": "Get the next eligible ticket for an agent.",
        "sprint": "Plan, view, and close sprints.",
        "start": "Assign and move a ticket into progress.",
        "update": "Update allowed ticket fields.",
        "validate": "Validate all tickets against schema.",
    }
