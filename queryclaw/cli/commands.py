"""CLI commands for QueryClaw."""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.text import Text

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.patch_stdout import patch_stdout

from queryclaw import __version__
from queryclaw.agent.loop import AgentLoop
from queryclaw.bus.events import OutboundMessage
from queryclaw.bus.queue import MessageBus
from queryclaw.channels.manager import ChannelManager
from queryclaw.config.loader import get_config_path, load_config, save_config
from queryclaw.config.schema import Config
from queryclaw.db.registry import AdapterRegistry
from queryclaw.providers.litellm_provider import LiteLLMProvider
from queryclaw.safety.policy import SafetyPolicy

app = typer.Typer(
    name="queryclaw",
    help="QueryClaw - AI-Native Database Agent",
    no_args_is_help=True,
)

console = Console()
EXIT_COMMANDS = {"exit", "quit", "/exit", "/quit", ":q"}


def version_callback(value: bool) -> None:
    """Print version and exit when --version is provided."""
    if value:
        console.print(f"queryclaw v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """QueryClaw CLI entry point."""


@app.command()
def onboard(
    config_path: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Custom config path (default: ~/.queryclaw/config.json).",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Overwrite existing config with defaults.",
    ),
) -> None:
    """Initialize QueryClaw configuration file."""
    path = config_path or get_config_path()

    if path.exists() and not overwrite:
        config = load_config(path)
        save_config(config, path)
        console.print(f"[green]Config refreshed:[/green] {path}")
        console.print("Existing values are preserved; missing fields are added.")
        return

    save_config(Config(), path)
    if path.exists() and overwrite:
        console.print(f"[green]Config reset:[/green] {path}")
    else:
        console.print(f"[green]Config created:[/green] {path}")

    console.print("\nNext steps:")
    console.print("- Configure your database in the `database` section")
    console.print("- Configure one LLM provider API key in `providers`")
    console.print("- Start chat: `queryclaw chat -m \"show tables\"`")
    console.print("- Or enable Feishu/DingTalk in `channels` and run: `queryclaw serve`")


def _make_provider(config: Config) -> LiteLLMProvider:
    """Create LLM provider from configuration."""
    model = config.agent.model
    provider_name = config.get_provider_name(model)
    provider_cfg = config.get_provider(model)

    if not provider_cfg or not provider_cfg.api_key:
        raise ValueError(
            "No LLM API key configured. "
            "Set one in ~/.queryclaw/config.json under providers."
        )

    return LiteLLMProvider(
        api_key=provider_cfg.api_key,
        api_base=config.get_api_base(model),
        default_model=model,
        extra_headers=provider_cfg.extra_headers,
        provider_name=provider_name,
    )


def _is_exit_command(command: str) -> bool:
    return command.strip().lower() in EXIT_COMMANDS


def _render_response(response: str, render_markdown: bool) -> None:
    body = Markdown(response) if render_markdown else Text(response)
    console.print()
    console.print("[cyan]QueryClaw[/cyan]")
    console.print(body)
    console.print()


async def _read_interactive_input(prompt_session: PromptSession) -> str:
    with patch_stdout():
        return await prompt_session.prompt_async(HTML("<b fg='ansiblue'>You:</b> "))


async def _confirm_operation(sql: str, message: str) -> bool:
    """Prompt user for confirmation of destructive operations."""
    console.print()
    console.print("[yellow]--- Confirmation Required ---[/yellow]")
    console.print(message)
    console.print()
    try:
        answer = input("Proceed? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return answer in ("y", "yes")


async def _run_chat(config: Config, message: str | None, render_markdown: bool) -> int:
    provider = _make_provider(config)
    adapter = await AdapterRegistry.create_and_connect(**config.database.model_dump())
    try:
        safety = SafetyPolicy(
            read_only=config.safety.read_only,
            max_affected_rows=config.safety.max_affected_rows,
            require_confirmation=config.safety.require_confirmation,
            allowed_tables=config.safety.allowed_tables,
            blocked_patterns=config.safety.blocked_patterns,
            audit_enabled=config.safety.audit_enabled,
        )
        agent = AgentLoop(
            provider=provider,
            db=adapter,
            model=config.agent.model,
            max_iterations=config.agent.max_iterations,
            temperature=config.agent.temperature,
            max_tokens=config.agent.max_tokens,
            safety_policy=safety,
            confirmation_callback=_confirm_operation,
        )

        if message:
            response = await agent.chat(message)
            _render_response(response, render_markdown)
            return 0

        console.print("[green]Interactive mode started.[/green] Type 'exit' to quit.")
        session = PromptSession(history=InMemoryHistory(), multiline=False)
        while True:
            try:
                user_input = (await _read_interactive_input(session)).strip()
            except (EOFError, KeyboardInterrupt):
                console.print("\n[dim]Bye.[/dim]")
                return 0

            if not user_input:
                continue
            if _is_exit_command(user_input):
                console.print("[dim]Bye.[/dim]")
                return 0

            response = await agent.chat(user_input)
            _render_response(response, render_markdown)
    finally:
        await adapter.close()


@app.command()
def chat(
    message: str | None = typer.Option(
        None,
        "--message",
        "-m",
        help="Single-turn message. If omitted, starts interactive mode.",
    ),
    config_path: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Custom config path (default: ~/.queryclaw/config.json).",
    ),
    no_markdown: bool = typer.Option(
        False,
        "--no-markdown",
        help="Render output as plain text instead of markdown.",
    ),
) -> None:
    """Start a chat session with QueryClaw."""
    config = load_config(config_path)

    try:
        exit_code = asyncio.run(_run_chat(config, message, render_markdown=not no_markdown))
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from e
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted.[/dim]")
        raise typer.Exit(code=130) from None
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")
        raise typer.Exit(code=1) from e

    if exit_code != 0:
        raise typer.Exit(code=exit_code)


async def _channel_confirm_callback(
    agent_ref: list,
    bus: MessageBus,
    sql: str,
    confirm_msg: str,
) -> bool:
    """Channel-mode confirmation: send prompt, await user reply (confirm/cancel)."""
    agent = agent_ref[0]
    if agent is None:
        return False
    msg = getattr(agent, "_current_msg", None)
    if msg is None:
        return False
    session_key = msg.session_key
    loop = asyncio.get_event_loop()
    future: asyncio.Future[bool] = loop.create_future()
    bus.register_confirmation(session_key, future, confirm_msg[:100])
    await bus.publish_outbound(
        OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=f"{confirm_msg}\n\n回复 **确认** 执行，**取消** 取消。",
        )
    )
    try:
        return await asyncio.wait_for(future, timeout=300)
    except asyncio.TimeoutError:
        bus.cancel_confirmation(session_key)
        return False


async def _run_serve(config: Config) -> None:
    """Run the multi-channel serve mode."""
    bus = MessageBus()
    manager = ChannelManager(config, bus)

    if not manager.enabled_channels:
        console.print("[red]Error:[/red] No channels enabled. Configure feishu or dingtalk in config.")
        raise typer.Exit(code=1)

    provider = _make_provider(config)
    adapter = await AdapterRegistry.create_and_connect(**config.database.model_dump())

    try:
        safety = SafetyPolicy(
            read_only=config.safety.read_only,
            max_affected_rows=config.safety.max_affected_rows,
            require_confirmation=config.safety.require_confirmation,
            allowed_tables=config.safety.allowed_tables,
            blocked_patterns=config.safety.blocked_patterns,
            audit_enabled=config.safety.audit_enabled,
        )
        agent_ref: list = [None]

        async def channel_confirm(sql: str, confirm_msg: str) -> bool:
            return await _channel_confirm_callback(agent_ref, bus, sql, confirm_msg)

        agent = AgentLoop(
            provider=provider,
            db=adapter,
            model=config.agent.model,
            max_iterations=config.agent.max_iterations,
            temperature=config.agent.temperature,
            max_tokens=config.agent.max_tokens,
            safety_policy=safety,
            confirmation_callback=channel_confirm,
            bus=bus,
        )
        agent_ref[0] = agent

        manager_task = asyncio.create_task(manager.start_all())
        agent_task = asyncio.create_task(agent.run())

        try:
            await asyncio.gather(manager_task, agent_task)
        except asyncio.CancelledError:
            pass
        finally:
            agent.stop()
            await manager.stop_all()
    finally:
        await adapter.close()


@app.command()
def serve(
    config_path: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Custom config path (default: ~/.queryclaw/config.json).",
    ),
) -> None:
    """Start QueryClaw in multi-channel mode (Feishu, DingTalk)."""
    config = load_config(config_path)

    try:
        asyncio.run(_run_serve(config))
    except KeyboardInterrupt:
        console.print("\n[dim]Shutting down...[/dim]")
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from e
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")
        raise typer.Exit(code=1) from e
