from pathlib import Path
from shutil import copy2, copytree, rmtree
import hashlib


def print_summary(stats, output_folder: Path, missing_count: int = 0):
    print("\n" + "=" * 60)
    print("                 JishAtlas Summary")
    print("=" * 60)

    print(f"📄 Files organized      : {stats['files_copied']}")
    print(f"📁 Folders created      : {len(stats['folders_created'])}")
    print(f"🗂️  Projects moved       : {stats['projects_copied']}")
    print(f"📦 Passthrough copied   : {stats['passthrough_copied']}")
    print(f"❌ Errors               : {stats['errors']}")

    print("\nOutput Folder:")
    print(f"  {output_folder}")

    print("=" * 60)

    if missing_count > 0:
        print(
            f"⚠️ Organization completed, but {missing_count} file(s) were not "
            "copied because the AI did not include them."
        )
    elif stats["errors"] == 0:
        print("✅ Organization completed successfully!")
    else:
        print("⚠️ Organization completed with errors.")


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


def create_organized_copy(results, main_dir, passthrough_dirs):
    folder_path = Path(main_dir)
    parent_dir = folder_path.parent

    new_folder = parent_dir / f"{folder_path.name}_Organised"

    # Rebuild from scratch: never merge stale content from a previous run
    if new_folder.exists():
        rmtree(new_folder)
    new_folder.mkdir(parents=True, exist_ok=True)

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
    for result in results:
        path_str = result.get("path")

        if not path_str:
            stats["errors"] += 1
            print("Failed to copy: result is missing a path")
            continue

        rel_path = Path(path_str)

        # Files inside passthrough dirs are copied with the whole directory
        if any(rel_path.is_relative_to(p) for p in passthrough_dirs):
            continue

        # Reject paths that escape the folder being organized
        source = _safe_source(folder_path, rel_path)

        if source is None:
            stats["errors"] += 1
            print(
                f"Failed to copy {result['path']}: path escapes the folder being organized"
            )
            continue

        # Reject AI-suggested paths that do not correspond to a real file
        # (the AI can drop path components or invent names on large folders).
        if not source.exists():
            stats["errors"] += 1
            print(
                f"Failed to copy {result['path']}: the AI suggested a path that "
                "was not found in the folder"
            )
            continue

        # Whole projects move as a single unit, keeping their name
        if result.get("type") == "project":
            suggested_folder = result.get("suggested_folder")

            if not suggested_folder:
                stats["errors"] += 1
                print(
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
                print(
                    f"Failed to copy project {source}: destination escapes the organized folder"
                )
                continue

            try:
                copytree(source, destination, dirs_exist_ok=True)
                stats["projects_copied"] += 1

            except Exception as e:
                stats["errors"] += 1
                print(f"Failed to copy project {source}: {e}")

            continue

        # Individual files inside a project root travel with the project
        if any(rel_path.is_relative_to(p) for p in project_paths):
            continue

        suggested_folder = result.get("suggested_folder")
        suggested_name = result.get("suggested_name")

        if not suggested_folder or not suggested_name:
            stats["errors"] += 1
            print(
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
            print(f"Failed to copy {source}: destination escapes the organized folder")
            continue

        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            stats["folders_created"].add(destination.parent)

            copy2(source, destination)

            stats["files_copied"] += 1

        except Exception as e:
            stats["errors"] += 1
            print(f"Failed to copy {source}: {e}")

    # Copy passthrough directories (node_modules, .venv, .git, ...)
    for directory in passthrough_dirs:
        # Passthrough dirs nested inside a project root travel with the project
        if any(directory.is_relative_to(p) for p in project_paths):
            continue

        source = folder_path / directory
        destination = new_folder / directory

        try:
            copytree(source, destination, dirs_exist_ok=True)
            stats["passthrough_copied"] += 1

        except Exception as e:
            stats["errors"] += 1
            print(f"Failed to copy {source}: {e}")

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
    print("\n🔍 Checking the organized copy is complete...")
    missing = verify_complete_copy(folder_path, new_folder)

    if missing:
        print(
            f"\n⚠️ The organized copy is missing {len(missing)} file(s) that "
            "the AI did not include."
        )
        for path in missing[:10]:
            print(f"   {path}")
        if len(missing) > 10:
            print(f"   ... and {len(missing) - 10} more")

    print_summary(stats, new_folder, missing_count=len(missing))


def apply_changes_same_folder(results, main_dir, passthrough_dirs):
    folder_path = Path(main_dir)

    new_folder, stats = create_organized_copy(
        results,
        main_dir,
        passthrough_dirs,
    )

    if stats["errors"] > 0:
        print("\nOrganization aborted because errors occurred.")
        print("The original folder has NOT been modified.")
        return

    # Safety check: never touch the original unless every file in it exists
    # in the organized copy (matched by content, not by path).
    print("\n🔍 Verifying the organized copy is complete...")
    missing = verify_complete_copy(folder_path, new_folder)

    if missing:
        print("\n❌ Safety check failed: the organized copy is missing files.")
        print("This usually means the AI analysis omitted some files when")
        print("the folder was large. The original folder was left untouched")
        print("to protect your data.")
        print()
        for path in missing[:10]:
            print(f"   {path}")
        if len(missing) > 10:
            print(f"   ... and {len(missing) - 10} more")
        print("\nThe original folder has NOT been modified.")
        print("\nYou can:")
        print("  • Re-run JishAtlas - AI results vary between runs.")
        print("  • Use 'Create Organized Copy' mode, which never touches the original.")
        print("  • Organize the folder in smaller batches.")
        return

    # Swap the organized copy into place. The original is only deleted after
    # the swap has fully succeeded, so nothing is lost if anything fails.
    backup = folder_path.with_name(f"{folder_path.name}.jishatlas_backup")

    if backup.exists():
        try:
            rmtree(backup)
        except Exception as e:
            print(f"\n⚠️ Could not remove stale backup {backup}: {e}")

    try:
        folder_path.rename(backup)
        new_folder.rename(folder_path)
    except Exception as e:
        print(f"\n❌ Failed to swap folders: {e}")

        # Try to restore the original in place
        if backup.exists() and not folder_path.exists():
            try:
                backup.rename(folder_path)
                print("The original folder has been restored.")
            except Exception:
                print(f"Your files are safe in: {backup}")
        elif folder_path.exists():
            print("The original folder is still in place and has NOT been modified.")
        elif backup.exists():
            print(f"Your files are safe in: {backup}")

        print("The original folder has NOT been replaced.")
        return

    try:
        rmtree(backup)
    except Exception as e:
        print(f"\n⚠️ Could not remove the backup folder: {e}")
        print(f"Your files are safe in: {backup}")

    print_summary(stats, folder_path)
