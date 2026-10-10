from pathlib import Path

from huggingface_hub import hf_hub_download
from rich.panel import Panel

from input import get_app_dir
from ui import console


APP_DIR = get_app_dir()
MODEL_DIR = APP_DIR / "models"


QWEN_MODEL = {
    "repo_id": "unsloth/Qwen3-1.7B-GGUF",
    "filename": "Qwen3-1.7B-Q4_K_M.gguf",
}


def ensure_model(repo_id: str, filename: str) -> Path:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    local_path = MODEL_DIR / filename

    if local_path.is_file():
        return local_path

    console.print(
        Panel.fit(
            f"""[bold cyan]🤖 Preparing Local AI[/bold cyan]

[dim]Model:[/dim] {filename}

[cyan]Downloading from Hugging Face...[/cyan]

[dim]This only happens once.[/dim]""",
            title="JishAtlas",
            border_style="cyan",
        )
    )

    try:
        downloaded_path = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            local_dir=str(MODEL_DIR),
        )

    except Exception as e:
        console.print(f"\n[bold red]❌ Model download failed:[/bold red]\n{e}")
        raise SystemExit(1)

    downloaded_path = Path(downloaded_path)

    if not downloaded_path.is_file():
        console.print(
            "[bold red]❌ Model download completed, "
            "but the model file could not be found.[/bold red]"
        )
        raise SystemExit(1)

    console.print("\n[bold green]✓ Local AI model ready![/bold green]\n")

    return downloaded_path


def ensure_qwen() -> Path:
    return ensure_model(
        QWEN_MODEL["repo_id"],
        QWEN_MODEL["filename"],
    )
