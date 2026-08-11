from llama_cpp import Llama, LlamaGrammar
from google import genai
from google.genai import types
from pathlib import Path
import os
import json
from dotenv import load_dotenv
from dataclasses import asdict
from rich.console import Console
from rich.panel import Panel
import time
from rich.status import Status
from installmodels import ensure_qwen

console = Console()

load_dotenv()


# --------------------------------------------------
# Prompt
# --------------------------------------------------


def build_prompt(files_json, folders_json, project_roots_json):
    return f"""
You are a file organization assistant.

TASK

Analyze the input items and suggest a clean, logical folder structure.
You are only making suggestions. Do not perform any filesystem operations.

RULES

1. Every input item must appear exactly once in the output.
2. Never omit, duplicate, or merge input items.
3. Reuse existing folders when they are a good fit.
4. You may create new folders when they improve organization.
5. Use nested relative folder paths when useful.
6. Use "/" as the folder separator.
7. Keep folder structures logical and reasonably shallow.
8. Group related items together instead of creating unnecessary folders.
9. Use clear, descriptive folder names.
10. Never change a file extension.
11. Suggested filenames should be concise and descriptive.
12. For source code and text files, use lowercase_with_underscores for suggested names.
13. Every final destination must be unique.
14. Never use absolute paths.

PROJECTS

The PROJECT ROOTS list contains directories that have been detected
as complete projects.

Any input file whose path is inside a project root belongs to that
project.

For project files:
- Do not rename the file.
- Do not move the file.
- Do not modify the file.
- Do not reorganize the project internally.

The only allowed action for a project is moving the entire project
root to a different parent folder.

Treat the project root as a single organization unit.

OUTPUT

Return ONLY a valid JSON array.

For a file:
{{
    "type": "file",
    "path": "games/dice.py",
    "suggested_folder": "Programming/Python/Games",
    "suggested_name": "dice_roller.py"
}}

For a project:
{{
    "type": "project",
    "path": "Downloads/WeatherApp",
    "suggested_folder": "Programming/Python"
}}

VALIDATION

Before responding, verify:
- Every input item appears exactly once.
- No two items have the same final destination.
- File extensions are unchanged.
- All suggested folders are relative paths.
- No absolute paths are present.
- The response contains only valid JSON.

PATH PRESERVATION

The "path" field is an identifier from the input data.

For every file, copy the "full_path" value EXACTLY as provided
in INPUT FILES.

NEVER shorten it.
NEVER remove parent folders.
NEVER use only the filename.
NEVER rename the path field.

The "path" in the output must match an input file's full_path
character-for-character.

Examples:

If the input contains:
"cpp_game/src/main.cpp"

The output MUST contain:
"path": "cpp_game/src/main.cpp"

NOT:
"path": "main.cpp"

If the input contains:
"school/math_notes.txt"

The output MUST contain:
"path": "school/math_notes.txt"

NOT:
"path": "math_notes.txt"

PROJECT TYPE RULE — ABSOLUTE

The PROJECT ROOTS list is authoritative.

A result may use:
"type": "project"
ONLY when its "path" EXACTLY matches one of the paths
in PROJECT ROOTS.

If a path is NOT present in PROJECT ROOTS:
- its type MUST be "file"
- NEVER classify it as a project
- NEVER infer that it is a project from its filename or contents

Examples:

PROJECT ROOTS:
[
    "cpp_game",
    "frontend_experiment"
]

Valid:
{{
    "type": "project",
    "path": "cpp_game",
    ...
}}

Valid:
{{
    "type": "file",
    "path": "Customer.accdb",
    ...
}}

INVALID:
{{
    "type": "project",
    "path": "Customer.accdb",
    ...
}}

INPUT FILES
{files_json}

EXISTING FOLDERS
{folders_json}

PROJECT ROOTS
{project_roots_json}
"""


# --------------------------------------------------
# Data preparation
# --------------------------------------------------


def prepare_ai_data(files, folders, project_roots):
    files_json = json.dumps(
        [asdict(file) for file in files],
        indent=2,
        ensure_ascii=False,
    )

    folders_json = json.dumps(
        [asdict(folder) for folder in folders],
        indent=2,
        ensure_ascii=False,
    )

    project_roots_json = json.dumps(
        [str(path) for path in project_roots],
        indent=2,
        ensure_ascii=False,
    )

    return files_json, folders_json, project_roots_json


# --------------------------------------------------
# Local AI
# --------------------------------------------------
LOCAL_JSON_SCHEMA = {
    "type": "array",
    "minItems": 1,
    "items": {
        "type": "object",
        "properties": {
            "type": {
                "type": "string",
                "enum": ["file", "project"],
            },
            "path": {
                "type": "string",
            },
            "suggested_folder": {
                "type": "string",
            },
            "suggested_name": {
                "type": "string",
            },
        },
        "required": [
            "type",
            "path",
            "suggested_folder",
        ],
    },
}


def create_local_grammar():
    return LlamaGrammar.from_json_schema(json.dumps(LOCAL_JSON_SCHEMA))


def load_local_model():
    os.environ["LLAMA_CHAT_TEMPLATE_KWARGS"] = (
        '{"enable_thinking": false}'
    )

    with console.status(
        "[bold cyan]🤖 Loading local AI model...[/bold cyan]",
        spinner="dots",
    ):
        llm = Llama(
            model_path=str(ensure_qwen()),
            n_ctx=16384,
            verbose=False,
        )

    console.print("[bold green]✓ Local AI ready![/bold green]")

    return llm

# --------------------------------------------------
# Path validation
# --------------------------------------------------


def sanitize_results(results, files):
    """Repair AI-suggested paths that do not match a real scanned file.

    The local model occasionally drops path components on larger folders
    (e.g. it returns "dir_1/nested_1.txt" when the real scanned path is
    "dir_1/sub/nested_1.txt"). Such paths would fail during the copy step
    with a confusing "Failed to copy ... [WinError 2]" error.

    When the basename matches exactly one scanned file, the path is
    rewritten to the real one so the file gets organized correctly.
    Ambiguous or unmatched paths are left untouched and will be reported
    as errors by the apply step.

    Returns a new list; the input list is not modified.
    """
    exact_paths = {
        Path(f.full_path).as_posix().lower(): f.full_path
        for f in files
    }
    by_name = {}
    for f in files:
        by_name.setdefault(f.name.lower(), []).append(f.full_path)

    repaired = 0
    cleaned = []

    for result in results:
        path = result.get("path")

        # Projects are left untouched: their paths must stay relative to the
        # folder being organized, which apply.py relies on. Only file paths
        # are repaired here.
        if result.get("type") == "project" or path is None:
            cleaned.append(result)
            continue

        norm = Path(path).as_posix().lower()
        if norm in exact_paths:
            cleaned.append(result)
            continue

        matches = by_name.get(Path(path).name.lower(), [])
        if len(matches) == 1:
            result = {**result, "path": matches[0]}
            repaired += 1

        cleaned.append(result)

    if repaired:
        console.print(
            f"[yellow]⚠️  Repaired {repaired} AI-suggested path(s) to match "
            "the scanned files.[/yellow]"
        )

    return cleaned


# --------------------------------------------------
# Shared output
# --------------------------------------------------


def print_results(results):
    console.print("\n[bold cyan]✓ AI analysis complete![/bold cyan]\n")

    console.rule("[bold cyan]Suggested Changes[/bold cyan]")

    for result in results:
        source = Path(result["path"])

        if result["type"] == "file":
            suggested_name = result.get(
                "suggested_name",
                source.name,
            )

            destination = Path(result["suggested_folder"]) / suggested_name

            title = f"📄 {source.name}"

        else:
            destination = Path(result["suggested_folder"]) / source.name

            title = f"📦 {source.name}"

        content = (
            f"[bold yellow]From[/bold yellow]\n"
            f"  {source}\n\n"
            f"[bold green]To[/bold green]\n"
            f"  {destination}"
        )

        console.print(
            Panel(
                content,
                title=title,
                border_style="cyan",
                padding=(0, 1),
            )
        )
        time.sleep(0.2)


# --------------------------------------------------
# Gemini
# --------------------------------------------------


def categorize_gemini(files, folders, passthrough_dirs, project_roots):

    print(f"✓ Found {len(files)} files in {len(folders)} folders")
    print(f"📦 Passthrough directories: {len(passthrough_dirs)}")
    print("\n🤖 Asking Gemini to analyze your files...")

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    files_json, folders_json, project_roots_json = prepare_ai_data(
        files,
        folders,
        project_roots,
    )

    prompt = build_prompt(
        files_json,
        folders_json,
        project_roots_json,
    )

    try:
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )

        results = json.loads(response.text)

    except json.JSONDecodeError:
        print("❌ Gemini returned invalid JSON.")
        raise SystemExit

    except Exception as e:
        print(f"❌ AI request failed: {e}")
        raise SystemExit

    results = sanitize_results(results, files)
    print_results(results)

    return results


# --------------------------------------------------
# Local
# --------------------------------------------------



def categorize_local(files, folders, passthrough_dirs, project_roots):

    print(f"✓ Found {len(files)} files in {len(folders)} folders")
    print(f"📦 Passthrough directories: {len(passthrough_dirs)}")
    print("\n🤖 Asking local AI to analyze your files...")

    files_json, folders_json, project_roots_json = prepare_ai_data(
        files,
        folders,
        project_roots,
    )

    prompt = build_prompt(
        files_json,
        folders_json,
        project_roots_json,
    )

    grammar = create_local_grammar()
    llm = load_local_model()

    try:
        with console.status(
    "[bold cyan]🧠 Analyzing your files...[/bold cyan]",
    spinner="dots",
):
            response = llm.create_chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": prompt,
                    }
                ],
                grammar=grammar,
                temperature=0.2,
            )

        results = json.loads(response["choices"][0]["message"]["content"])

    except json.JSONDecodeError:
        print("❌ Local AI returned invalid JSON.")
        raise SystemExit

    except Exception as e:
        print(f"❌ AI request failed: {e}")
        raise SystemExit

    results = sanitize_results(results, files)
    print_results(results)

    return results
