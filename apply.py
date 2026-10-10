from pathlib import Path
from shutil import copy2, copytree, rmtree
import hashlib
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.progress import track
from ui import console


def _say(message=""):
    """Print literal text cleanly while a Rich progress display is active."""
    console.print(Text(str(message)))



def print_summary(stats, output_folder: Path, missing_count: int = 0):
    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="dim")
    summary.add_column(justify="right", style="bold")
    summary.add_row("Files organized", str(stats["files_copied"]))
    summary.add_row("Folders created", str(len(stats["folders_created"])))
    summary.add_row("Projects kept together", str(stats["projects_copied"]))
    summary.add_row("Protected folders copied", str(stats["passthrough_copied"]))
    summary.add_row("Items with errors", str(stats["errors"]))
    summary.add_row("Output folder", Text(str(output_folder), style="cyan", overflow="fold"))

    if missing_count > 0:
        heading = "Completed with missing files"
        border = "yellow"
    elif stats["errors"] == 0:
        heading = "Organization complete"
        border = "green"
    else:
        heading = "Completed with errors"
        border = "yellow"

    console.print(
        Panel(
            summary,
            title=f"[bold {border}]✦ {heading}[/bold {border}]",
            border_style=border,
            padding=(1, 2),
        )
    )
    if missing_count > 0:
        console.print(
            f"[yellow]The copy is missing {missing_count} file(s) that the AI did not include.[/yellow]"
        )


def _safe_source(folder_path: Path, rel_path: Path) -> Path | None:
    """Return the real source path, or None if it escapes folder_path."""
    source = folder_path / rel_path

    try:
        resolved = source.resolve()
        root = folder_path.resolve()
    except OSError:
        return None

    if resolved != root and root not in resolved.parents:
        return None

    return source


def _safe_destination(new_folder: Path, suggested_folder, name) -> Path | None:
    """Return the destination path, or None if it escapes new_folder."""
    destination = new_folder / suggested_folder / name

    try:
        resolved = destination.resolve()
        root = new_folder.resolve()
    except OSError:
        return None

    if resolved != root and root not in resolved.parents:
        return None

    return destination


def _new_output_folder(folder_path: Path) -> Path:
    """Create a fresh output folder without replacing a previous run."""
    base = folder_path.with_name(f"{folder_path.name}_Organised")
    candidate = base
    suffix = 2

    while True:
        try:
            candidate.mkdir(parents=True, exist_ok=False)
            return candidate
        except FileExistsError:
            candidate = base.with_name(f"{base.name} ({suffix})")
            suffix += 1


def create_organized_copy(results, main_dir, passthrough_dirs):
    folder_path = Path(main_dir)

    # Never delete or merge into a previous output. Each run gets a new folder.
    new_folder = _new_output_folder(folder_path)

    stats = {
        "files_copied": 0,
        "folders_created": set(),
        "projects_copied": 0,
        "passthrough_copied": 0,
        "errors": 0,
    }

    project_paths = [
        Path(result["path"])
        for result in results
        if result.get("type") == "project" and result.get("path")
    ]

    # Copy AI-organized files
    for result in track(results, description="[cyan]Organizing files and projects", console=console):
        path_str = result.get("path")

        if not path_str:
            stats["errors"] += 1
            _say("Failed to copy: result is missing a path")
            continue

        rel_path = Path(path_str)

        # Files inside passthrough dirs are copied with the whole directory
        if any(rel_path.is_relative_to(p) for p in passthrough_dirs):
            continue

        # Reject paths that escape the folder being organized
        source = _safe_source(folder_path, rel_path)

        if source is None:
            stats["errors"] += 1
            _say(
                f"Failed to copy {result['path']}: path escapes the folder being organized"
            )
            continue

        # Reject AI-suggested paths that do not correspond to a real file
        # (the AI can drop path components or invent names on large folders).
        if not source.exists():
            stats["errors"] += 1
            _say(
                f"Failed to copy {result['path']}: the AI suggested a path that "
                "was not found in the folder"
            )
            continue

        # Whole projects move as a single unit, keeping their name
        if result.get("type") == "project":
            suggested_folder = result.get("suggested_folder")

            if not suggested_folder:
                stats["errors"] += 1
                _say(
                    f"Failed to copy project {source}: result is missing a suggested folder"
                )
                continue

            destination = _safe_destination(
                new_folder,
                suggested_folder,
                rel_path.name,
            )

            if destination is None:
                stats["errors"] += 1
                _say(
                    f"Failed to copy project {source}: destination escapes the organized folder"
                )
                continue

            if destination.exists():
                stats["errors"] += 1
                _say(f"Failed to copy project {source}: destination already exists")
                continue

            try:
                copytree(source, destination)
                stats["projects_copied"] += 1

            except Exception as e:
                stats["errors"] += 1
                _say(f"Failed to copy project {source}: {e}")

            continue

        # Individual files inside a project root travel with the project
        if any(rel_path.is_relative_to(p) for p in project_paths):
            continue

        suggested_folder = result.get("suggested_folder")
        suggested_name = result.get("suggested_name")

        if not suggested_folder or not suggested_name:
            stats["errors"] += 1
            _say(
                f"Failed to copy {source}: result is missing a suggested folder or name"
            )
            continue

        destination = _safe_destination(
            new_folder,
            suggested_folder,
            suggested_name,
        )

        if destination is None:
            stats["errors"] += 1
            _say(f"Failed to copy {source}: destination escapes the organized folder")
            continue

        if destination.exists():
            stats["errors"] += 1
            _say(f"Failed to copy {source}: destination already exists")
            continue

        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            stats["folders_created"].add(destination.parent)

            copy2(source, destination)

            stats["files_copied"] += 1

        except Exception as e:
            stats["errors"] += 1
            _say(f"Failed to copy {source}: {e}")

    # Copy passthrough directories (node_modules, .venv, .git, ...)
    for directory in track(
        passthrough_dirs,
        description="[cyan]Preserving protected folders",
        console=console,
    ):
        # Passthrough dirs nested inside a project root travel with the project
        if any(directory.is_relative_to(p) for p in project_paths):
            continue

        source = folder_path / directory
        destination = new_folder / directory

        try:
            copytree(source, destination)
            stats["passthrough_copied"] += 1

        except Exception as e:
            stats["errors"] += 1
            _say(f"Failed to copy {source}: {e}")

    return new_folder, stats


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()

    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)

    return digest.hexdigest()


def _file_hash_counts(root: Path) -> dict:
    counts = {}

    for path in root.rglob("*"):
        if not path.is_file():
            continue

        try:
            digest = _hash_file(path)
        except OSError:
            continue

        counts[digest] = counts.get(digest, 0) + 1

    return counts


def verify_complete_copy(source_dir: Path, target_dir: Path) -> list:
    """Return paths of files in source_dir that are missing from target_dir.

    Files may be renamed or reorganized in the copy, so items are matched by
    content hash instead of by path.
    """
    target_counts = _file_hash_counts(target_dir)

    missing = []

    for path in source_dir.rglob("*"):
        if not path.is_file():
            continue

        try:
            digest = _hash_file(path)
        except OSError:
            # Unreadable files (locked, permission denied, broken links) were
            # already counted as copy errors, so they are not reported as
            # "missing" here.
            continue

        if target_counts.get(digest, 0) > 0:
            target_counts[digest] -= 1
        else:
            missing.append(str(path))

    return missing


def apply_changes_diff_folder(results, main_dir, passthrough_dirs):
    folder_path = Path(main_dir)

    new_folder, stats = create_organized_copy(
        results,
        main_dir,
        passthrough_dirs,
    )

    # The AI can omit files entirely when a folder has many of them. Detect
    # any missing files so an incomplete copy is never mistaken for a
    # complete organization. The original folder is untouched in copy mode,
    # so this is a warning rather than an abort.
    with console.status(
        "[bold cyan]Checking every copied file...[/bold cyan]",
        spinner="dots",
    ):
        missing = verify_complete_copy(folder_path, new_folder)

    if missing:
        _say(
            f"\n⚠️ The organized copy is missing {len(missing)} file(s) that "
            "the AI did not include."
        )
        for path in missing[:10]:
            _say(f"   {path}")
        if len(missing) > 10:
            _say(f"   ... and {len(missing) - 10} more")

    print_summary(stats, new_folder, missing_count=len(missing))


def apply_changes_same_folder(results, main_dir, passthrough_dirs):
    folder_path = Path(main_dir)

    new_folder, stats = create_organized_copy(
        results,
        main_dir,
        passthrough_dirs,
    )

    if stats["errors"] > 0:
        _say("\nOrganization aborted because errors occurred.")
        _say("The original folder has NOT been modified.")
        return

    # Safety check: never touch the original unless every file in it exists
    # in the organized copy (matched by content, not by path).
    with console.status(
        "[bold cyan]Verifying every file before replacing the original...[/bold cyan]",
        spinner="dots",
    ):
        missing = verify_complete_copy(folder_path, new_folder)

    if missing:
        _say("\n❌ Safety check failed: the organized copy is missing files.")
        _say("This usually means the AI analysis omitted some files when")
        _say("the folder was large. The original folder was left untouched")
        _say("to protect your data.")
        _say()
        for path in missing[:10]:
            _say(f"   {path}")
        if len(missing) > 10:
            _say(f"   ... and {len(missing) - 10} more")
        _say("\nThe original folder has NOT been modified.")
        _say("\nYou can:")
        _say("  • Re-run JishAtlas - AI results vary between runs.")
        _say("  • Use 'Create Organized Copy' mode, which never touches the original.")
        _say("  • Organize the folder in smaller batches.")
        return

    # Swap the organized copy into place. The original is only deleted after
    # the swap has fully succeeded, so nothing is lost if anything fails.
    backup_base = folder_path.with_name(f"{folder_path.name}.jishatlas_backup")
    backup = backup_base
    suffix = 2
    while backup.exists():
        backup = backup_base.with_name(f"{backup_base.name} ({suffix})")
        suffix += 1

    try:
        folder_path.rename(backup)
        new_folder.rename(folder_path)
    except Exception as e:
        _say(f"\n❌ Failed to swap folders: {e}")

        # Try to restore the original in place
        if backup.exists() and not folder_path.exists():
            try:
                backup.rename(folder_path)
                _say("The original folder has been restored.")
            except Exception:
                _say(f"Your files are safe in: {backup}")
        elif folder_path.exists():
            _say("The original folder is still in place and has NOT been modified.")
        elif backup.exists():
            _say(f"Your files are safe in: {backup}")

        _say("The original folder has NOT been replaced.")
        return

    try:
        rmtree(backup)
    except Exception as e:
        _say(f"\n⚠️ Could not remove the backup folder: {e}")
        _say(f"Your files are safe in: {backup}")

    print_summary(stats, folder_path)
