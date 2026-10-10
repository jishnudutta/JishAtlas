# JishAtlas

JishAtlas is a terminal application that uses Local AI or Google Gemini to
create file organization plans. It scans a selected directory, displays the
proposed changes, and applies them only after confirmation.

## Requirements

- Windows for the packaged executable
- Python 3.13 or later to run from source
- Internet access to use Gemini or download the Local AI model
- A Gemini API key to use the Gemini backend

Local AI runs on the computer. Its performance depends on available memory and
CPU resources.

## Run the Windows executable

Start `dist/JishAtlas.exe`. At the folder prompt, enter the full path to the
directory to organize, such as `C:\Users\name\Documents\Downloads`.

Choose an AI backend and an organization mode. Review the generated plan, then
confirm whether to apply it. The default mode creates a separate organized copy.
The in-place mode replaces the selected directory only after a complete copy
has been verified.

At the folder prompt, enter `k` to manage the Gemini API key or `q` to quit.
The backend menu also has an option to set or change the key.

## Run from source

```powershell
git clone https://github.com/jishnudutta/JishAtlas.git
cd JishAtlas
uv sync
uv run python main.py
```

Alternatively, create a Python 3.13+ virtual environment and install the
project with `pip install .`, then run `python main.py`.

## Workflow

1. Select a directory.
2. Scan files and folders. Text files are read as UTF-8, up to 1,200 characters
   per file. Binary and unreadable files remain in the scan without a content
   sample.
3. Detect software projects and protected directories.
4. Analyze the scan with the selected backend and display the proposed plan.
5. Apply the plan after confirmation, either to a new copy or in place.

Detected projects are treated as single units: their internal files are not
reorganized. Directories named `.git`, `node_modules`, `__pycache__`, `.venv`,
`venv`, `build`, `dist`, `.vscode`, `.vs`, `obj`, or `.idea` are excluded from
the scan and preserved as directories during copying.

Before replacing the original in in-place mode, JishAtlas verifies that every
readable source file exists in the organized copy by comparing file hashes. If
verification or copying fails, the original directory is left in place.

## AI backends and data handling

### Local AI

Local AI uses the `Qwen3-1.7B-Q4_K_M.gguf` model from
`unsloth/Qwen3-1.7B-GGUF`. JishAtlas downloads it on first use and stores it in
`%LOCALAPPDATA%\JishAtlas\models\` on Windows. File samples are summarized
locally, then the scan is divided into batches to fit the model context.

The context size defaults to 32,768 tokens. Set `JISHATLAS_CONTEXT_TOKENS` to
an integer from 4,096 through 40,960 to change it. Invalid values fall back to
the default. For source runs, this setting can be placed in the project `.env`
file. Packaged runs can use an environment variable.

### Gemini

Gemini requires an internet connection and API key. The request includes the
scanned relative paths, folder and project information, and up to 1,200
characters of UTF-8 text content per readable file. Do not use this backend for
folders whose contents should not be sent to Google.

The API key is stored as plain text in `.env` when running from source. In the
packaged executable, it is stored in `%LOCALAPPDATA%\JishAtlas\.env`. Keep this
file private and do not commit it to Git. An existing `GEMINI_API_KEY`
environment variable can also provide the key.

## Build the Windows executable

On Windows, double-click `build_exe.bat`. It prepares the Python build
environment, generates the executable icon from the SVG source, builds
`dist/JishAtlas.exe`, and runs the packaged startup smoke check. The PyInstaller
spec collects llama.cpp native libraries required by Local AI at runtime.

For a manual build with `uv`:

```powershell
uv sync --group dev
uv run python assets/make_icon.py
uv run pyinstaller --clean JishAtlas.spec
uv run pytest -q --basetemp=.build-tmp/pytest tests/test_exe_smoke.py
```

The smoke check exercises executable startup and skips the Local AI end-to-end
case when the model has not been downloaded. Run the full test suite with:

```powershell
uv run pytest -q --basetemp=.build-tmp/pytest
```

## Project files

- `main.py` — terminal workflow
- `scanner.py` — directory scanning, project detection, and Local AI setup
- `ai_analysis.py` — prompts, validation, and backend analysis
- `apply.py` — copy, verification, and in-place application
- `input.py` — interactive prompts and key management
- `JishAtlas.spec` — PyInstaller configuration
- `build_exe.bat` — Windows build and packaged startup check
- `assets/` — editable SVG brand assets and generated executable icon
- `tests/` — unit and packaged executable checks

## License

See [LICENSE](LICENSE).
