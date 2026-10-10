from pathlib import Path
import os
import sys

from dotenv import load_dotenv, set_key
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from ui import console


def get_app_dir():
    return Path(os.getenv("LOCALAPPDATA", Path.home())) / "JishAtlas"


ENV_FILE = (
    get_app_dir() / ".env"
    if getattr(sys, "frozen", False)
    else Path(".env")
)


def _gemini_key():
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE, override=False)
    return os.getenv("GEMINI_API_KEY", "")


def _masked_gemini_key():
    key = _gemini_key()
    return f"••••{key[-4:]}" if key else "Not set"


def _prompt_for_gemini_key():
    console.print(
        Panel.fit(
            "Gemini sends file names, folder paths, and local summaries to Google.\n"
            "The key is saved locally in [bold].env[/bold].\n\n"
            "Enter a key, or leave it blank to return without changing it.",
            title="[bold cyan]Gemini API key[/bold cyan]",
            border_style="cyan",
        )
    )
    api_key = Prompt.ask("[bold]Gemini API key[/bold]", password=True).strip()
    if not api_key:
        console.print("[dim]No key entered. Returning to the previous menu.[/dim]")
        return False

    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    set_key(ENV_FILE, "GEMINI_API_KEY", api_key)
    os.environ["GEMINI_API_KEY"] = api_key
    console.print(
        f"\n[bold green]✓ Gemini key saved[/bold green]  "
        f"[dim]{_masked_gemini_key()}[/dim]"
    )
    return True


def setup_gemini_api_key():
    """Ask for a Gemini key when one is missing; return False if cancelled."""
    if _gemini_key():
        return True
    return _prompt_for_gemini_key()


def change_gemini_api_key():
    """Replace the saved Gemini key without displaying the full value."""
    console.print(
        Panel.fit(
            f"Current key: [bold]{_masked_gemini_key()}[/bold]\n\n"
            "Your new key is hidden while typing and saved locally in .env.",
            title="[bold cyan]Gemini API key[/bold cyan]",
            border_style="cyan",
        )
    )
    return _prompt_for_gemini_key()


def get_folder():
    while True:
        folder = Prompt.ask(
            "[bold]Enter the full path of the folder to organize[/bold] "
            "[dim](k = Gemini key, q = quit)[/dim]"
        ).strip().strip('"')

        if folder.lower() in ("q", "quit", "exit"):
            return None
        if folder.lower() in ("k", "key", "settings"):
            change_gemini_api_key()
            continue

        root_dir = Path(folder).expanduser()
        if not root_dir.exists():
            console.print(
                "[bold red]Folder does not exist.[/bold red] "
                "Enter another path or q to quit.\n"
            )
            continue
        if not root_dir.is_dir():
            console.print(
                "[bold red]That path is a file, not a folder.[/bold red] "
                "Enter another path or q to quit.\n"
            )
            continue

        root_dir = root_dir.resolve()
        console.print(
            Panel.fit(
                f"[bold]Ready to organize[/bold]\n[cyan]{root_dir}[/cyan]",
                border_style="cyan",
            )
        )
        return root_dir


def ask_run_again():
    return Confirm.ask("\n[bold]Organize another folder?[/bold]", default=True)


def select_ai_backend():
    """Choose an AI backend or update Gemini credentials before a run."""
    while True:
        key_status = _masked_gemini_key()
        key_action = "Change Gemini API key" if key_status != "Not set" else "Set Gemini API key"
        options = Table.grid(padding=(0, 2))
        options.add_column(style="bold cyan", justify="right")
        options.add_column()
        options.add_row("1", "Local AI  [dim]· offline; files stay on this computer[/dim]")
        options.add_row(
            "2",
            "Gemini  [dim]· online; sends file names, paths, and summaries to Google[/dim]",
        )
        options.add_row("3", f"{key_action}  [dim]· current: {key_status}[/dim]")
        console.print(
            Panel(
                options,
                title="[bold cyan]Choose how JishAtlas should organize[/bold cyan]",
                border_style="cyan",
                padding=(1, 2),
            )
        )

        choice = Prompt.ask(
            "[bold]Choose an option[/bold]",
            choices=["1", "2", "3"],
            default="1",
        )
        if choice == "3":
            if key_status == "Not set":
                _prompt_for_gemini_key()
            else:
                change_gemini_api_key()
            continue
        if choice == "2" and not setup_gemini_api_key():
            continue
        return {"1": "local", "2": "gemini"}[choice]


def select_organization_mode():
    options = Table.grid(padding=(0, 2))
    options.add_column(style="bold green", justify="right")
    options.add_column()
    options.add_row("1", "Organize in place  [dim]· moves files in the selected folder[/dim]")
    options.add_row("2", "Create an organized copy  [bold green]· recommended[/bold green]")
    console.print(
        Panel(
            options,
            title="[bold green]Choose where to organize[/bold green]",
            border_style="green",
            padding=(1, 2),
        )
    )
    choice = Prompt.ask(
        "[bold]Choose an option[/bold]",
        choices=["1", "2"],
        default="2",
    )
    return {"1": "in_place", "2": "copy"}[choice]


def ask_apply_changes():
    console.print(
        Panel.fit(
            "Review the suggested changes above. Nothing moves until you approve.",
            title="[bold yellow]Ready to apply[/bold yellow]",
            border_style="yellow",
        )
    )
    return Confirm.ask("[bold]Apply these changes?[/bold]", default=False)
