"""
Advanced splash screen template for JishAtlas.

NOTE:
This is an enhanced scaffold that you can extend with richer animations.
"""

import shutil
import threading
import time

from rich.align import Align
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
from rich.text import Text

console = Console()

LARGE_LOGO = r"""
      ██╗██╗███████╗██╗  ██╗ █████╗ ████████╗██╗      █████╗ ███████╗
      ██║██║██╔════╝██║  ██║██╔══██╗╚══██╔══╝██║     ██╔══██╗██╔════╝
      ██║██║███████╗███████║███████║   ██║   ██║     ███████║███████╗
 ██   ██║██║╚════██║██╔══██║██╔══██║   ██║   ██║     ██╔══██║╚════██║
 ╚█████╔╝██║███████║██║  ██║██║  ██║   ██║   ███████╗██║  ██║███████║
  ╚════╝ ╚═╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝╚══════╝
"""

SMALL_LOGO = "JISHATLAS"

class SplashScreen:
    def __init__(self, version="0.1 Alpha"):
        self.version = version
        self.layout = Layout()
        self.layout.split_column(Layout(name="banner", ratio=5),
                                 Layout(name="progress", ratio=2))
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold cyan]{task.description}"),
            BarColumn(),
            console=console,
            expand=True,
        )
        self.task = self.progress.add_task("Starting...", total=100)
        self.running = False
        self.live = None
        self.bright = True

    def _logo(self):
        w = shutil.get_terminal_size((80,24)).columns
        return LARGE_LOGO if w >= 90 else SMALL_LOGO

    def _panel(self):
        style = "bold bright_cyan" if self.bright else "dim cyan"
        title = Text(self._logo(), style=style)
        subtitle = Text(
            "\nAI-powered intelligent file organization\n"
            f"Version {self.version}",
            justify="center",
        )
        return Panel(
            Align.center(Group(title, subtitle)),
            border_style="cyan",
            title="JISHATLAS",
        )

    def _animate(self):
        while self.running:
            self.bright = not self.bright
            self.layout["banner"].update(self._panel())
            self.layout["progress"].update(self.progress)
            self.live.update(self.layout)
            time.sleep(0.45)

    def start(self):
        console.clear()

        # Typing animation
        typed = ""
        for ch in "JISHATLAS":
            typed += ch
            console.print(f"[bold cyan]{typed}█[/]", justify="center")
            time.sleep(0.08)
            console.clear()

        self.running = True
        self.live = Live(self.layout, console=console, refresh_per_second=30)
        self.live.start()
        threading.Thread(target=self._animate, daemon=True).start()

    def set_status(self, text, advance=20):
        self.progress.update(self.task, description=text, advance=advance)

    def finish(self):
        self.progress.update(self.task, completed=100, description="Ready")
        time.sleep(0.6)
        self.running = False
        self.live.stop()
        console.print(self._panel())
        console.print("[bold green]✓ Startup Complete[/bold green]")

def show(version="0.1 Alpha"):
    splash = SplashScreen(version)
    splash.start()
    for step in [
        "Loading Qwen...",
        "Preparing scanner...",
        "Loading prompts...",
        "Ready..."
    ]:
        splash.set_status(step, 25)
        time.sleep(1)
    splash.finish()

if __name__ == "__main__":
    show()
