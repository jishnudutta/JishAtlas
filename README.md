# JishAtlas

### AI-powered intelligent file organization

**Local AI • Google Gemini • Privacy First**

Organize files intelligently with offline Local AI or enhanced cloud-powered analysis.

## What is JishAtlas?

JishAtlas is a simple file organization tool that uses AI to help clean up messy folders.

Instead of manually deciding where every file should go, JishAtlas looks at your files, understands their purpose, and suggests a more useful folder structure.

You can review all suggested changes before anything is applied.

JishAtlas is designed to be simple, safe, and easy to use.

## Features

- AI-powered file and folder organization
- Local AI support for offline organization
- Google Gemini support for cloud-based analysis
- Automatic project detection
- Protects detected projects from being reorganized internally
- File content analysis for better organization
- Conservative file renaming
- Existing folder reuse
- Nested folder organization when useful
- Passthrough directories for folders such as `node_modules`, `.git`, and build directories
- Preview all changes before applying them
- Organized-copy mode that leaves the original folder untouched
- Validation of AI suggestions before filesystem changes
- Automatic local model downloading
- Simple terminal-based interface

## How it works

JishAtlas follows a simple process:

```text
Select a folder
      |
      v
Scan files and folders
      |
      v
Detect projects and protected directories
      |
      v
Analyze file contents
      |
      v
Generate an organization plan
      |
      v
Review suggested changes
      |
      v
Apply changes
```

The AI only creates an organization plan. JishAtlas itself handles the actual filesystem operations and validates the suggestions before applying them.

## AI Backends

### Local AI

JishAtlas can use a local Qwen model to analyze your files.

The model runs on your computer, so your files do not need to be sent to a cloud service for the analysis.

The model is downloaded automatically the first time you use the Local AI backend and stored in your local JishAtlas application data directory.

### Google Gemini

JishAtlas can also use Google Gemini for cloud-based analysis.

Gemini can provide stronger reasoning and is useful when your computer does not have enough resources for local AI.

Using Gemini requires a Gemini API key and an internet connection.

Your API key is stored locally in your `.env` file.

## Safe by design

File organization tools need to be careful because a mistake can affect many files.

JishAtlas therefore separates AI suggestions from filesystem operations.

Before applying changes, it checks things such as:

- Whether the source file actually exists
- Whether the path came from the scanned files
- Whether a project is actually a detected project
- Whether destination paths are valid
- Whether files would be duplicated
- Whether files would unexpectedly overwrite existing files
- Whether the original file extension is preserved

For the safest option, JishAtlas can create an organized copy instead of changing the original folder.

## Projects

JishAtlas can detect common software projects using project markers such as:

```text
.git
package.json
pyproject.toml
Cargo.toml
go.mod
pom.xml
CMakeLists.txt
*.sln
*.csproj
pubspec.yaml
composer.json
```

When a project is detected, JishAtlas treats it as a single unit.

It does not reorganize the files inside the project. If the project needs to be moved, the entire project is moved together.

## Passthrough directories

Some directories should normally never be reorganized.

JishAtlas can skip directories such as:

```text
.git
node_modules
__pycache__
.venv
venv
build
dist
.vscode
.idea
```

These directories are preserved rather than analyzed and reorganized like normal files.

## Installation

For the Windows release, download the latest JishAtlas executable from the GitHub Releases page.

You do not need to install Python separately when using the packaged executable.

On first use of Local AI, JishAtlas will download the required model automatically.

## Running from source

If you want to run JishAtlas directly from Python:

```bash
git clone https://github.com/your-username/JishAtlas.git
cd JishAtlas

python -m venv .venv
```

Activate the environment on Windows:

```powershell
.venv\Scripts\activate
```

Install the dependencies:

```bash
pip install -r requirements.txt
```

Then run:

```bash
python main.py
```

## Gemini setup

If you select the Gemini backend, JishAtlas will ask for your API key if one has not already been configured.

The key is stored locally as:

```text
.env
```

Do not commit this file to Git.

Your `.gitignore` should contain:

```gitignore
.env
models/
```

## Local model storage

Downloaded local models are stored outside the application directory, under the user's local application data folder.

On Windows, this is typically:

```text
%LOCALAPPDATA%\JishAtlas\models\
```

This keeps the executable small and allows the model to be reused when the application is updated.

## Requirements

For Local AI, performance depends on your computer's available RAM and CPU.

The default v0.1 model is a small quantized Qwen model intended to work on relatively modest systems.

Gemini requires:

- Internet access
- A valid Gemini API key

## Current status

JishAtlas is currently in **v0.1 Alpha**.

The core organization workflow is functional, but the project is still being actively developed. You should keep backups of important files when testing it, especially when using the in-place organization mode.

## Roadmap

Future versions may include:

- Better local models
- Image understanding
- More advanced content analysis
- More organization strategies
- Improved model management
- Additional AI providers
- A graphical interface
- More extensive platform support

The goal is to keep JishAtlas useful without making it unnecessarily complicated.

## Contributing

Contributions, bug reports, and suggestions are welcome.

If you find a problem, please provide:

1. What you were trying to organize
2. Which AI backend you used
3. What happened
4. Any relevant error message

Avoid sharing private files, API keys, or other sensitive information in issues.

## License

This project is licensed under the terms of the license included in this repository.

---

**JishAtlas** is built around a simple idea: let AI handle the tedious part of organizing files while keeping the user in control of what actually happens to their data.
