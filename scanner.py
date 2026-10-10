from pathlib import Path
import os
import warnings
from dataclasses import dataclass
from fnmatch import fnmatch
from llama_cpp import Llama
from installmodels import ensure_qwen


@dataclass
class Folder:
    name: str
    full_path: str


@dataclass
class File:
    name: str
    full_path: str
    parent_folder: str
    contents: str | None


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
    ".idea",
    ".git",
}


PROJECT_FILE_MARKERS = {
    # =========================
    # Very High Confidence (100)
    # =========================
    ".git": 100,
    "package.json": 100,
    "pyproject.toml": 100,
    "Cargo.toml": 100,
    "go.mod": 100,
    "pom.xml": 100,
    "pubspec.yaml": 100,
    "composer.json": 100,
    "Package.swift": 100,
    # =========================
    # High Confidence (90)
    # =========================
    "CMakeLists.txt": 90,
    "build.gradle": 90,
    "build.gradle.kts": 90,
    "settings.gradle": 90,
    "settings.gradle.kts": 90,
    "Gemfile": 90,
    "mix.exs": 90,
    "stack.yaml": 90,
    "cabal.project": 90,
    # =========================
    # Medium-High (75)
    # =========================
    "requirements.txt": 75,
    "Pipfile": 75,
    "setup.py": 75,
    "setup.cfg": 75,
    "Cargo.lock": 75,
    "go.sum": 75,
    "composer.lock": 75,
    "Package.resolved": 75,
    # =========================
    # Build / Tooling (60)
    # =========================
    "Makefile": 60,
    "meson.build": 60,
    "conanfile.py": 60,
    "conanfile.txt": 60,
    "Dockerfile": 60,
    "docker-compose.yml": 60,
    "docker-compose.yaml": 60,
    "compose.yml": 60,
    "compose.yaml": 60,
    # =========================
    # JavaScript Tooling (50)
    # =========================
    "package-lock.json": 50,
    "yarn.lock": 50,
    "pnpm-lock.yaml": 50,
    "bun.lockb": 50,
    "tsconfig.json": 50,
    "jsconfig.json": 50,
    "vite.config.js": 50,
    "vite.config.ts": 50,
    "webpack.config.js": 50,
    "rollup.config.js": 50,
    "next.config.js": 50,
    "nuxt.config.ts": 50,
    "astro.config.mjs": 50,
    "svelte.config.js": 50,
    "angular.json": 50,
    # =========================
    # Python Tooling (45)
    # =========================
    "poetry.lock": 45,
    "Pipfile.lock": 45,
    "tox.ini": 45,
    "pytest.ini": 45,
    "mypy.ini": 45,
    "ruff.toml": 45,
    ".flake8": 45,
    # =========================
    # Documentation (20)
    # =========================
    "README.md": 20,
    "README.rst": 20,
    "README.txt": 20,
    "LICENSE": 15,
    "LICENSE.md": 15,
    "CHANGELOG.md": 15,
    "CONTRIBUTING.md": 15,
    # =========================
    # Repository Metadata (10)
    # =========================
    ".gitignore": 10,
    ".gitattributes": 10,
    ".editorconfig": 10,
    ".pre-commit-config.yaml": 10,
    # =========================
    # Misc
    # =========================
    "Directory.Build.props": 60,
    "Directory.Build.targets": 60,
    "global.json": 60,
    "main.tf": 70,
    "terraform.tf": 70,
    "ProjectVersion.txt": 80,
}

PROJECT_DIR_MARKERS = {
    # Very High
    ".git": 100,
    # Strong indicators
    "src": 40,
    "tests": 35,
    "test": 35,
    "__tests__": 35,
    "include": 35,
    "lib": 30,
    "app": 30,
    "apps": 30,
    "packages": 30,
    # Supporting evidence
    "docs": 20,
    "examples": 20,
    # Unity
    "Assets": 80,
    "ProjectSettings": 80,
    "Packages": 60,
    # Unreal
    "Content": 80,
    "Config": 60,
    "Source": 80,
    # Android
    "gradle": 60,
}

PROJECT_PATTERNS = {
    "*.sln": 100,
    "*.csproj": 100,
    "*.vbproj": 100,
    "*.fsproj": 100,
    "*.xcodeproj": 100,
    "*.xcworkspace": 100,
    "*.uproject": 100,
}

llm = None
DEFAULT_CONTEXT_TOKENS = 32768
MAX_CONTEXT_TOKENS = 40960
MAX_FILE_SAMPLE_CHARS = 1200


def _configured_context_tokens() -> int:
    """Read the local model context size, falling back safely if invalid."""
    raw_value = os.getenv("JISHATLAS_CONTEXT_TOKENS", str(DEFAULT_CONTEXT_TOKENS))
    try:
        value = int(raw_value)
    except ValueError:
        warnings.warn(
            "JISHATLAS_CONTEXT_TOKENS must be a number; using the default.",
            RuntimeWarning,
        )
        return DEFAULT_CONTEXT_TOKENS

    if not 4096 <= value <= MAX_CONTEXT_TOKENS:
        warnings.warn(
            f"JISHATLAS_CONTEXT_TOKENS must be between 4096 and {MAX_CONTEXT_TOKENS}; "
            "using the default.",
            RuntimeWarning,
        )
        return DEFAULT_CONTEXT_TOKENS
    return value


def get_text_model():
    global llm

    if llm is None:
        os.environ["LLAMA_CHAT_TEMPLATE_KWARGS"] = (
            '{"enable_thinking": false}'
        )
        model_path = ensure_qwen()

        llm = Llama(
            model_path=str(model_path),
            n_ctx=_configured_context_tokens(),
            verbose=False,
        )

    return llm


def summarize_content(content: str) -> str:
    if not content:
        return ""

    model = get_text_model()

    prompt = f"""
Summarize the following file content in one concise sentence.

Focus on what the file actually contains or does.
Do not mention the filename.
Do not guess information that is not present.
Return ONLY the summary.

FILE CONTENT:
{content[:MAX_FILE_SAMPLE_CHARS]}
"""

    response = model.create_chat_completion(
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        temperature=0.2,
        max_tokens=32,
    )

    return response["choices"][0]["message"]["content"].strip()


def scan_directory(root_dir, summarize=True):
    folders = []
    files = []

    passthrough_dirs = []

    for current_root, dirs, filenames in os.walk(root_dir):

        # Remove passthrough directories so os.walk() won't enter them
        ignored = []

        for d in dirs[:]:  # iterate over a copy
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
            folders.append(Folder(name=d, full_path=str(full.relative_to(root_dir))))

        # Files
        for filename in filenames:

            path = Path(current_root) / filename

            try:
                with path.open("r", encoding="utf-8") as source_file:
                    text = source_file.read(MAX_FILE_SAMPLE_CHARS)
                content = summarize_content(text) if summarize else text.strip()
            except (UnicodeDecodeError, OSError):
                # Binary content or an unreadable/locked file (e.g. one open in
                # another program) is skipped instead of crashing the scan.
                content = None

            files.append(
                File(
                    name=path.name,
                    full_path=str(path.relative_to(root_dir)),
                    parent_folder=str(path.parent.relative_to(root_dir)),
                    contents=content,
                )
            )
    return files, folders, passthrough_dirs


def detect_projects(root_dir):
    project_roots = set()

    for current_root, dirs, files in os.walk(root_dir):
        current_path = Path(current_root)

        score = 0

        # File markers
        for filename in files:
            score += PROJECT_FILE_MARKERS.get(filename, 0)

        # Directory markers
        for dirname in dirs:
            score += PROJECT_DIR_MARKERS.get(dirname, 0)

        # Pattern markers
        for filename in files:
            for pattern, weight in PROJECT_PATTERNS.items():
                if fnmatch(filename, pattern):
                    score += weight

        if score >= 100:
            project_roots.add(current_path)

        # Count markers on this folder first (notably .git), then prune
        # generated/dependency trees so their contents are not traversed.
        dirs[:] = [dirname for dirname in dirs if dirname not in PASSTHROUGH_DIRS]

    return project_roots
