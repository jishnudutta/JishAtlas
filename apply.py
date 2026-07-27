from pathlib import Path
from shutil import copy2, copytree, rmtree


def print_summary(stats, output_folder: Path):
    print("\n" + "=" * 60)
    print("                 JishAtlas Summary")
    print("=" * 60)

    print(f"📄 Files organized      : {stats['files_copied']}")
    print(f"📁 Folders created      : {len(stats['folders_created'])}")
    print(f"📦 Passthrough copied   : {stats['passthrough_copied']}")
    print(f"❌ Errors               : {stats['errors']}")

    print("\nOutput Folder:")
    print(f"  {output_folder}")

    print("=" * 60)

    if stats["errors"] == 0:
        print("✅ Organization completed successfully!")
    else:
        print("⚠️ Organization completed with errors.")


def create_organized_copy(results, main_dir, passthrough_dirs):
    folder_path = Path(main_dir)
    parent_dir = folder_path.parent

    new_folder = parent_dir / f"{folder_path.name}_Organised"
    new_folder.mkdir(parents=True, exist_ok=True)

    stats = {
        "files_copied": 0,
        "folders_created": set(),
        "passthrough_copied": 0,
        "errors": 0,
    }

    # Copy AI-organized files
    for result in results:
        source = folder_path / result["path"]
        destination = (
            new_folder
            / result["suggested_folder"]
            / result["suggested_name"]
        )

        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            stats["folders_created"].add(destination.parent)

            copy2(source, destination)

            stats["files_copied"] += 1

        except Exception as e:
            stats["errors"] += 1
            print(f"Failed to copy {source}: {e}")

    # Copy passthrough directories
    for directory in passthrough_dirs:

        source = folder_path / directory
        destination = new_folder / directory

        try:
            copytree(source, destination, dirs_exist_ok=True)
            stats["passthrough_copied"] += 1

        except Exception as e:
            stats["errors"] += 1
            print(f"Failed to copy {source}: {e}")

    return new_folder, stats


def apply_changes_diff_folder(results, main_dir, passthrough_dirs):

    new_folder, stats = create_organized_copy(
        results,
        main_dir,
        passthrough_dirs,
    )

    print_summary(stats, new_folder)


def apply_changes_same_folder(results, main_dir, passthrough_dirs):

    folder_path = Path(main_dir)

    new_folder, stats = create_organized_copy(
        results,
        main_dir,
        passthrough_dirs,
    )

    if stats["errors"] == 0:
        rmtree(folder_path)
        new_folder.rename(folder_path)
        print_summary(stats, folder_path)
    else:
        print("\nOrganization aborted because errors occurred.")
        print("The original folder has NOT been modified.")