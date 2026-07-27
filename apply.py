from pathlib import Path
from shutil import copy2
from shutil import copytree
from shutil import rmtree

def apply_changes_same_folder(results, main_dir, passthrough_dirs):

    stats = {
    "files_copied": 0,
    "folders_created": set(),
    "passthrough_copied": 0,
    "errors": 0
}

    folder_path = Path(main_dir)

    parent_dir = folder_path.parent

    new_folder = parent_dir / f"{folder_path.name}_Organised"

    new_folder.mkdir(parents=True, exist_ok=True)

    for result in results:

        source = folder_path / result["path"]

        destination = (
            new_folder
            / result["suggested_folder"]
            / result["suggested_name"]
        )

        # Create destination folders
        destination.parent.mkdir(parents=True, exist_ok=True)

    for directory in passthrough_dirs:
    
            source = folder_path / directory
            destination = new_folder / directory
    
            copytree(source, destination, dirs_exist_ok=True)  

    # Copy and rename
    copy2(source, destination)
    rmtree(main_dir)
    new_folder.rename(folder_path.name)
  

def apply_changes_diff_folder(results, main_dir, passthrough_dirs):

    stats = {
    "files_copied": 0,
    "folders_created": set(),
    "passthrough_copied": 0,
    "errors": 0
}

    folder_path = Path(main_dir)

    parent_dir = folder_path.parent

    new_folder = parent_dir / f"{folder_path.name}_Organised"

    new_folder.mkdir(parents=True, exist_ok=True)

    for result in results:

        source = folder_path / result["path"]

        destination = (
            new_folder
            / result["suggested_folder"]
            / result["suggested_name"]
        )

        # Create destination folders
        destination.parent.mkdir(parents=True, exist_ok=True)

        # Copy and rename
        copy2(source, destination)

    for directory in passthrough_dirs:

        source = folder_path / directory
        destination = new_folder / directory

        copytree(source, destination, dirs_exist_ok=True)