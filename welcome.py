"""Fast, branded terminal welcome screen for JishAtlas."""

from rich.align import Align
from rich.console import Group
from rich.panel import Panel
from rich.text import Text
from ui import console


def show(version="0.1 Alpha"):
    wordmark = Text("JishAtlas", style="bold bright_cyan", justify="center")
    tagline = Text(
        "Make room for the work that matters.\n"
        "Local AI when privacy matters · Gemini when you choose it",
        style="white",
        justify="center",
    )
    footer = Text(f"{version}   ·   Review every change before it is applied", style="dim", justify="center")

    console.print(
        Panel(
            Align.center(Group(wordmark, Text(), tagline, Text(), footer)),
            title="[bold cyan]FILE ORGANIZATION, WITH YOU IN CONTROL[/bold cyan]",
            border_style="cyan",
            padding=(1, 3),
        )
    )
