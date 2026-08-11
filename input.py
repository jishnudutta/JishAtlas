from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from dotenv import load_dotenv, set_key
import os

console = Console()

ENV_FILE = Path(".env")

def get_app_dir():
    APP_DIR = (
    Path(os.getenv("LOCALAPPDATA", Path.home()))
    / "JishAtlas")

    return APP_DIR

def setup_gemini_api_key():
    """Ask for and save the Gemini API key if it is not already configured."""

    load_dotenv(ENV_FILE)

    import os

    if os.getenv("GEMINI_API_KEY"):
        return

    console.print(
        Panel.fit(
            "[bold cyan]Gemini API Setup[/bold cyan]\n\n"
            "JishAtlas needs a Gemini API key to use the Gemini backend.\n"
            "Your key will be stored locally in [bold].env[/bold].\n\n"
            "[yellow]Never share your API key with anyone.[/yellow]",
            title="JishAtlas",
            border_style="cyan",
        )
    )

    api_key = Prompt.ask(
        "\n[bold]Enter your Gemini API key[/bold]",
        password=True,
    ).strip()

    if not api_key:
        console.print("[bold red]❌ API key cannot be empty.[/bold red]")
        raise SystemExit

    set_key(
        ENV_FILE,
        "GEMINI_API_KEY",
        api_key,
    )

    console.print("\n[bold green]✓ Gemini API key saved to .env[/bold green]")


def get_folder():
    folder = Prompt.ask(
        "📂 Enter the folder to organize (or 'q' to quit)"
    ).strip()

    # The user can quit from the folder prompt.
    if folder.lower() in ("q", "quit", "exit"):
        return None

    root_dir = Path(folder)

    if not root_dir.exists():
        console.print("[red]❌ Folder does not exist.[/red]")
        raise SystemExit

    if not root_dir.is_dir():
        console.print("[red]❌ Path is not a folder.[/red]")
        raise SystemExit

    console.print(f"\nSelected folder: [cyan]{root_dir.resolve()}[/cyan]\n")

    return root_dir


def ask_run_again():
    """Ask whether to organize another folder (default: yes)."""
    return Confirm.ask(
        "\n🔄 Organize another folder?",
        default=True,
    )


def select_ai_backend():
    console.print(
        Panel.fit(
            """[bold cyan]Select AI Backend[/bold cyan]

[bold]1. Local AI[/bold]
• Runs completely offline
• Files stay on your computer

[bold]2. Gemini[/bold]
• Cloud AI
• Requires internet
• Files are sent to Google for analysis
""",
            title="JishAtlas",
            border_style="cyan",
        )
    )

    choice = Prompt.ask(
        "\nSelect AI backend",
        choices=["1", "2"],
        default="1",
    )

    return {
        "1": "local",
        "2": "gemini",
    }[choice]


def select_organization_mode():
    console.print(
        Panel.fit(
            """[bold cyan]Organization Mode[/bold cyan]

[bold]1. Organize in Place[/bold]
• Move and rename files in the selected folder.

[bold]2. Create Organized Copy[/bold] [green](Recommended)[/green]
• Create a new organized folder.
• Original files remain unchanged.
""",
            title="JishAtlas",
            border_style="green",
        )
    )

    choice = Prompt.ask(
        "\nSelect organization mode",
        choices=["1", "2"],
        default="2",
    )

    return {
        "1": "in_place",
        "2": "copy",
    }[choice]


def ask_apply_changes():
    return Confirm.ask(
        "\nApply these changes?",
        default=False,
    )
