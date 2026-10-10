import sys
import ctypes

ctypes.windll.kernel32.SetConsoleTitleW(
    "JishAtlas"
)
# Windows consoles may default to cp1252, which cannot encode the emoji
# used throughout the CLI. Force UTF-8 so the output does not crash.
# This must run before importing the other modules so their rich Console
# instances are constructed with UTF-8 output.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from apply import apply_changes_diff_folder
from apply import apply_changes_same_folder
from input import get_folder
from input import (
    select_ai_backend,
    ask_apply_changes,
    ask_run_again,
    select_organization_mode,
)
from scanner import scan_directory
from scanner import detect_projects
from welcome import show
from ai_analysis import categorize_gemini, categorize_local
from ui import console

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

#       ██╗██╗███████╗██╗  ██╗ █████╗ ████████╗██╗      █████╗ ███████╗
#       ██║██║██╔════╝██║  ██║██╔══██╗╚══██╔══╝██║     ██╔══██╗██╔════╝
#       ██║██║███████╗███████║███████║   ██║   ██║     ███████║███████╗
#  ██   ██║██║╚════██║██╔══██║██╔══██║   ██║   ██║     ██╔══██║╚════██║
#  ╚█████╔╝██║███████║██║  ██║██║  ██║   ██║   ███████╗██║  ██║███████║
#   ╚════╝ ╚═╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝╚══════╝

#                          J I S H A T L A S

#                 AI-powered intelligent file organization

# Powered by Gemini and Qwen | Version 0.1 Alpha

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main():
    show()

    try:
        while True:
            folder = get_folder()

            # The user quit from the folder prompt.
            if folder is None:
                break

            backend = select_ai_backend()

            console.rule("[bold cyan]01  ·  Scan and understand[/bold cyan]")
            with console.status(
                "[bold cyan]Reading files and looking for protected projects...[/bold cyan]",
                spinner="dots",
            ):
                files, folders, passthrough_dirs = scan_directory(
                    folder,
                    summarize=(backend == "local"),
                )
                project_roots = detect_projects(folder)

            console.print(
                f"[green]✓[/green] [bold]{len(files)}[/bold] files  ·  "
                f"[bold]{len(folders)}[/bold] folders  ·  "
                f"[bold]{len(project_roots)}[/bold] protected projects  ·  "
                f"[bold]{len(passthrough_dirs)}[/bold] skipped system folders\n"
            )

            console.rule("[bold cyan]02  ·  Build an organization plan[/bold cyan]")
            if backend == "gemini":
                results = categorize_gemini(
                    files,
                    folders,
                    passthrough_dirs,
                    project_roots,
                )
            elif backend == "local":
                results = categorize_local(
                    files,
                    folders,
                    passthrough_dirs,
                    project_roots,
                )

            console.rule("[bold green]03  ·  Choose how to apply it[/bold green]")
            organization_mode = select_organization_mode()

            apply_changes = ask_apply_changes()

            if apply_changes:
                if organization_mode == "copy":
                    apply_changes_diff_folder(
                        results,
                        folder,
                        passthrough_dirs,
                    )
                else:
                    apply_changes_same_folder(
                        results,
                        folder,
                        passthrough_dirs,
                    )
            else:
                console.print("[yellow]Changes were not applied.[/yellow]")

            # Keep the program open instead of closing abruptly after the
            # results: let the user organize another folder or quit.
            if not ask_run_again():
                break

    except (KeyboardInterrupt, EOFError):
        # Ctrl+C or exhausted piped input: exit quietly instead of a
        # traceback. SystemExit is deliberately not caught here - it is
        # raised by AI setup when a service fails or returns unusable output.
        pass

    console.print("\n[bold cyan]Thanks for using JishAtlas.[/bold cyan] [dim]See you next time![/dim]")


if __name__ == "__main__":
    main()
