import sys
from input import setup_gemini_api_key
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
from input import select_ai_backend, ask_apply_changes, select_organization_mode
from scanner import scan_directory
from scanner import detect_projects
from welcome import show
from ai_analysis import categorize_gemini, categorize_local

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

show()

folder = get_folder()

files, folders, passthrough_dirs = scan_directory(folder)
project_roots = detect_projects(folder)

backend = select_ai_backend()

if backend == "gemini":
    setup_gemini_api_key()
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
    print("Operation cancelled.")
