from llama_cpp import LlamaGrammar
from google import genai
from google.genai import types
from pathlib import Path
import os
import sys
import json
from dotenv import load_dotenv
from dataclasses import asdict
from rich.table import Table
from rich import box
from rich.text import Text
from ui import console
import scanner

if not getattr(sys, "frozen", False):
    load_dotenv()
from input import ENV_FILE

load_dotenv(ENV_FILE, override=False)


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
15. The output MUST include every file from INPUT FILES. A file inside a
    project root is covered by that project's entry.
16. Omitting a file means it would be left behind when the changes are
    applied. Never omit a file because you are unsure - include it with
    your best guess for its folder.

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
- Every file in INPUT FILES appears in the output, either as its own
  "file" entry or inside a "project" entry.
- The output array is not empty when INPUT FILES is not empty.
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
        separators=(",", ":"),
        ensure_ascii=False,
    )

    folders_json = json.dumps(
        [asdict(folder) for folder in folders],
        separators=(",", ":"),
        ensure_ascii=False,
    )

    project_roots_json = json.dumps(
        [str(path) for path in project_roots],
        separators=(",", ":"),
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
    with console.status(
        "[bold cyan]🤖 Loading local AI model...[/bold cyan]",
        spinner="dots",
    ):
        llm = scanner.get_text_model()

    console.print("[bold green]✓ Local AI ready![/bold green]")

    return llm


def _local_prompt_batches(files, folders, project_roots, llm):
    """Pack files into prompts that fit the model context and output reserve."""
    context_size = llm.n_ctx()
    output_reserve = min(4096, max(1024, context_size // 8))
    input_budget = context_size - output_reserve
    folder_paths = sorted({folder.full_path for folder in folders})
    roots_json = json.dumps(
        [str(path) for path in sorted(project_roots, key=str)],
        separators=(",", ":"),
        ensure_ascii=False,
    )

    def render(file_batch, available_folders):
        files_json = json.dumps(
            [asdict(file) for file in file_batch],
            separators=(",", ":"),
            ensure_ascii=False,
        )
        folders_json = json.dumps(
            available_folders,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        prompt = build_prompt(files_json, folders_json, roots_json)
        return prompt, len(llm.tokenize(prompt.encode("utf-8"), add_bos=True))

    _, base_tokens = render([], folder_paths)
    if base_tokens > input_budget:
        # Original parent paths remain in each File record; use them as the
        # folder candidates if a very large tree exhausts the shared context.
        folder_paths = sorted(
            {
                file.parent_folder
                for file in files
                if file.parent_folder and file.parent_folder != "."
            }
        )
        _, base_tokens = render([], folder_paths)
    if base_tokens > input_budget:
        raise ValueError(
            "The folder and project list is larger than the local model's "
            "usable context. Increase JISHATLAS_CONTEXT_TOKENS or organize "
            "a smaller folder."
        )

    batches = []
    current = []
    estimated_tokens = base_tokens
    for file in files:
        encoded = json.dumps(
            asdict(file), separators=(",", ":"), ensure_ascii=False
        )
        item_tokens = len(llm.tokenize(encoded.encode("utf-8"), add_bos=False)) + 12
        if current and estimated_tokens + item_tokens > input_budget:
            batches.append(current)
            current = []
            estimated_tokens = base_tokens
        current.append(file)
        estimated_tokens += item_tokens
    if current:
        batches.append(current)

    prompts = []

    def append_fitting(batch):
        prompt, token_count = render(batch, folder_paths)
        if token_count <= input_budget:
            prompts.append((prompt, batch))
        elif len(batch) > 1:
            midpoint = len(batch) // 2
            append_fitting(batch[:midpoint])
            append_fitting(batch[midpoint:])
        else:
            # File contents help classification but are optional when one
            # unusually long path or record would otherwise exceed context.
            compact_file = type(batch[0])(
                **{**asdict(batch[0]), "contents": None}
            )
            prompt, token_count = render([compact_file], folder_paths)
            if token_count > input_budget:
                raise ValueError(
                    f"The path '{batch[0].full_path}' is too large for the "
                    "local model context."
                )
            prompts.append((prompt, [compact_file]))

    for batch in batches:
        append_fitting(batch)
    return prompts

# --------------------------------------------------
# Path validation
# --------------------------------------------------


def sanitize_results(results, files):
    """Repair or drop AI-suggested paths that do not match a real scanned file.

    The local model occasionally drops path components on larger folders
    (e.g. it returns "dir_1/nested_1.txt" when the real scanned path is
    "dir_1/sub/nested_1.txt"). Such paths would fail during the copy step
    with a confusing "Failed to copy ... [WinError 2]" error.

    When the basename matches exactly one scanned file, the path is
    rewritten to the real one so the file gets organized correctly.
    Paths that still cannot be matched (ambiguous basename, invented name,
    or a missing path) are dropped: keeping them would only surface as
    "the AI suggested a path that was not found" errors during the apply
    step. The real file is then added back by complete_results() in its
    original folder, so nothing is lost.

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
    dropped = 0
    cleaned = []

    for result in results:
        # Projects are left untouched: their paths must stay relative to the
        # folder being organized, which apply.py relies on. Only file paths
        # are repaired here.
        if result.get("type") == "project":
            cleaned.append(result)
            continue

        path = result.get("path")
        if not path:
            dropped += 1
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
            continue

        dropped += 1

    if repaired:
        console.print(
            f"[yellow]⚠️  Repaired {repaired} AI-suggested path(s) to match "
            "the scanned files.[/yellow]"
        )

    if dropped:
        console.print(
            f"[yellow]⚠️  Dropped {dropped} AI-suggested path(s) that could "
            "not be matched to a scanned file; the real files will be kept "
            "in their original folders.[/yellow]"
        )

    return cleaned


# --------------------------------------------------
# Result completion
# --------------------------------------------------


def complete_results(results, files):
    """Add back any scanned file the AI omitted from its analysis.

    Small models routinely drop files when a folder contains many of them.
    An omitted file would fail the apply-step safety check and block an
    in-place organization, so each omitted file is added back with its
    current folder and name. The organized copy is then always complete
    and no data is ever lost.

    Files that live inside a project root returned as a "project" travel
    with the project copy, so they are skipped here.

    Returns a new list; the input list is not modified.
    """
    covered = set()
    covered_projects = []

    for result in results:
        path = result.get("path")
        if not path:
            continue
        if result.get("type") == "project":
            covered_projects.append(Path(path))
        else:
            covered.add(Path(path).as_posix().lower())

    added = []

    for f in files:
        rel = Path(f.full_path)
        norm = rel.as_posix().lower()

        if norm in covered:
            continue

        # Inside a project root that is already returned as a "project":
        # the project copy carries it, no individual entry needed.
        if any(rel.is_relative_to(p) for p in covered_projects):
            continue

        added.append(
            {
                "type": "file",
                "path": f.full_path,
                "suggested_folder": f.parent_folder or ".",
                "suggested_name": f.name,
            }
        )
        covered.add(norm)

    if added:
        console.print(
            f"[yellow]⚠️  The AI omitted {len(added)} file(s); they will be "
            "kept in their original folders.[/yellow]"
        )

    return results + added


# --------------------------------------------------
# Shared output
# --------------------------------------------------


def print_results(results):
    console.print("\n[bold cyan]✓ AI analysis complete![/bold cyan]\n")

    if not results:
        console.print("[dim]There are no changes to review.[/dim]")
        return

    table = Table(
        title="Suggested changes  ·  review before applying",
        box=box.ROUNDED,
        border_style="cyan",
        header_style="bold cyan",
        row_styles=["", "dim"],
        expand=True,
    )
    table.add_column("Item", style="bold", no_wrap=True)
    table.add_column("Current location", overflow="fold")
    table.add_column("Planned location", style="green", overflow="fold")

    for result in results:
        source = Path(result["path"])

        if result["type"] == "file":
            suggested_name = result.get(
                "suggested_name",
                source.name,
            )

            destination = Path(result["suggested_folder"]) / suggested_name

            item_type = "FILE"

        else:
            destination = Path(result["suggested_folder"]) / source.name

            item_type = "PROJECT"

        table.add_row(item_type, Text(str(source)), Text(str(destination)))

    console.print(table)


# --------------------------------------------------
# Gemini
# --------------------------------------------------


def categorize_gemini(files, folders, passthrough_dirs, project_roots):
    if not files and not project_roots:
        console.print("[dim]No files or projects found to organize.[/dim]")
        return []

    console.print(
        f"[dim]Preparing {len(files)} files, {len(folders)} folders, and "
        f"{len(project_roots)} protected projects for Gemini.[/dim]"
    )

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
        with console.status(
            "[bold cyan]☁  Gemini is building your organization plan...[/bold cyan]",
            spinner="dots",
        ):
            client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
            response = client.models.generate_content(
                model="gemini-3.1-flash-lite",
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )

        results = json.loads(response.text)

    except json.JSONDecodeError:
        console.print("[bold red]❌ Gemini returned invalid JSON.[/bold red]")
        raise SystemExit

    except Exception as e:
        console.print(f"[bold red]❌ AI request failed:[/bold red] {e}")
        raise SystemExit

    results = sanitize_results(results, files)
    results = complete_results(results, files)
    print_results(results)

    return results


# --------------------------------------------------
# Local
# --------------------------------------------------



def categorize_local(files, folders, passthrough_dirs, project_roots):
    if not files and not project_roots:
        console.print("[dim]No files or projects found to organize.[/dim]")
        return []

    console.print(
        f"[dim]Preparing {len(files)} files, {len(folders)} folders, and "
        f"{len(project_roots)} protected projects for Local AI.[/dim]"
    )

    grammar = create_local_grammar()
    llm = load_local_model()
    raw_results = []
    response_budget = min(4096, max(512, llm.n_ctx() // 8))

    try:
        with console.status(
            "[bold cyan]Packing files into efficient context-sized batches...[/bold cyan]",
            spinner="dots",
        ):
            prompt_batches = _local_prompt_batches(files, folders, project_roots, llm)
        for index, (prompt, _) in enumerate(prompt_batches, start=1):
            with console.status(
                f"[bold cyan]🧠 Analyzing batch {index}/{len(prompt_batches)}...[/bold cyan]",
                spinner="dots",
            ):
                response = llm.create_chat_completion(
                    messages=[{"role": "system", "content": prompt}],
                    grammar=grammar,
                    temperature=0.2,
                    max_tokens=response_budget,
                )

            raw_results.extend(
                json.loads(response["choices"][0]["message"]["content"])
            )

    except json.JSONDecodeError:
        console.print("[bold red]❌ Local AI returned invalid JSON.[/bold red]")
        raise SystemExit

    except Exception as e:
        console.print(f"[bold red]❌ AI request failed:[/bold red] {e}")
        raise SystemExit

    # Project roots may be repeated across batches. Keep one result per source
    # path before validating the complete plan against the original scan.
    unique_results = []
    seen = set()
    for result in raw_results:
        key = (
            result.get("type"),
            str(result.get("path", "")).replace("\\", "/").lower(),
        )
        if key not in seen:
            seen.add(key)
            unique_results.append(result)

    results = sanitize_results(unique_results, files)
    results = complete_results(results, files)
    print_results(results)

    return results
