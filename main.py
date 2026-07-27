from google import genai
from dotenv import load_dotenv
import os
from pathlib import Path
from google.genai import types
import json

from apply import apply_changes_diff_folder 
from apply import apply_changes_same_folder 

load_dotenv()

folders = []
files = []

PASSTHROUGH_DIRS = {
    "build",
    "dist",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".vscode",
    ".vs",
    "obj",
    ".idea"
}

passthrough_dirs = []

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

folder = input("Enter the folder path: ")

root_dir = Path(folder)

for current_root, dirs, filenames in os.walk(root_dir):

    # Remove passthrough directories so os.walk() won't enter them
    ignored = []

    for d in dirs[:]:              # iterate over a copy
        if d in PASSTHROUGH_DIRS:
            ignored.append(d)
            dirs.remove(d)

    # Remember ignored directories
    for d in ignored:
        full = Path(current_root) / d
        passthrough_dirs.append(full.relative_to(root_dir))

    # Normal folders
    for d in dirs:
        full = Path(current_root) / d
        folders.append({
            "name": d,
            "full_path": str(full.relative_to(root_dir))
        })

    # Files
    for filename in filenames:

        path = Path(current_root) / filename

        try:
            MAX_CHARS = 5000
            content = path.read_text(encoding="utf-8")[:MAX_CHARS]
        except UnicodeDecodeError:
            content = None

        files.append({
            "parent_folder": str(path.parent.relative_to(root_dir)),
            "name": path.name,
            "full_path": str(path.relative_to(root_dir)),
            "contents": content
        })

files_json = json.dumps(files, indent=2, ensure_ascii=False)
folders_json = json.dumps(folders, indent=2, ensure_ascii=False)
    
prompt = f"""
You are an expert files and folders organiser.

Analyze the files and suggest an intuitive folder structure.

Use the existing folder hierarchy as a guide, not as a strict rule.

Reuse existing folders whenever they are a good fit.

If a better organization would require creating new folders or nesting folders more deeply, you may do so.

You may return multi-level relative folder paths using "/" as the separator.

Keep the hierarchy logical and easy to navigate. Avoid creating unnecessary or excessively deep folder structures.

Merge related topics together instead of creating many small folders with only one file unless there is a strong reason.

Prefer meaningful, descriptive folder names.

The goal is to produce the most organized and maintainable folder structure possible, even if that means reorganizing the existing hierarchy.

Rules:

- Preserve every file exactly once.
- Do not omit any file.
- Do not duplicate any file.
- Never change the file extension.
- Every file must have a unique destination path.
- suggested_folder must be a relative path (never absolute).
- Use "/" as the path separator.
- Return only JSON.

When renaming files:

- Preserve the original extension.
- Use descriptive but concise names.
- Use lowercase_with_underscores for source code and text files.
- Do not include spaces at the beginning or end.

Folder hierarchy should normally be between 2 and 4 levels deep.

Only exceed this if absolutely necessary.

Before returning your answer, verify that:

- every input file appears exactly once
- no destination path is duplicated
- every suggested name preserves the extension
- every suggested folder is relative
- every suggested folder uses "/" separators

Return ONLY valid JSON.

[
  {{
    "type": "file",
    "path": "games/dice.py",
    "suggested_folder": "scripts/games",
    "suggested_name": "dice_roller.py"
  }}
]
Files:
{files_json}

Existing Folders:
{folders_json}
"""

response = client.models.generate_content(
    model="gemini-3.1-flash-lite",
    contents=prompt,
    config=types.GenerateContentConfig(
        response_mime_type="application/json"
    )
)


results = json.loads(response.text)

for result in results:
    print(f"""
📄 {Path(result["path"]).name}

Rename:
  → {result["suggested_name"]}

Move to:
  → {result["suggested_folder"]}
══════════════════════════════════════════════════════
""")

apply = input("Apply changes? (Y/N): ").strip().upper()

if apply == "Y":
    mode = input(
        "1. Create organized copy\n"
        "2. Organize in place\n"
        "Choice (1/2): "
    ).strip()

    if mode == "1":
        apply_changes_diff_folder(results, folder, passthrough_dirs)

    elif mode == "2":
        print(json.dumps(results[0], indent=2))
        apply_changes_same_folder(results, folder, passthrough_dirs)

    else:
        print("Invalid choice.")

elif apply == "N":
    print("Cancelled.")

else:
    print("Please enter Y or N.")