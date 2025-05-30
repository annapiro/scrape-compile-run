import os
import shutil

from dotenv import load_dotenv
import pandas as pd
from tqdm import tqdm

from .compiler import is_executable
from .db_handler import initialize, wrapup, match_folder_to_row

load_dotenv()
SOURCE_DIR = os.path.join(*os.getenv('SOURCE_DIR').split('/'))
BUILD_DIR = os.path.join(*os.getenv('COMPILE_DIR').split('/'))


def copy_source_files(source: str, target: str):
    source_path = os.path.join(SOURCE_DIR, source)
    counter = 0
    for root, _, files in os.walk(source_path):
        for filename in files:
            file, ext = os.path.splitext(filename)
            if 'readme' in file.lower() or ext == '.c' or ext == '.h':
                filepath = os.path.join(root, filename)
                destination_folder = os.path.join(target, os.path.relpath(root, start=SOURCE_DIR))
                os.makedirs(destination_folder, exist_ok=True)
                shutil.copy(filepath, destination_folder)
                counter += 1
    print(f"{counter} source files")


def copy_build_files(source: str, target: str):
    source_path = os.path.join(BUILD_DIR, source)
    counter = 0
    for root, _, files in os.walk(source_path):
        for filename in files:
            filepath = os.path.join(root, filename)
            if is_executable(filepath):
                destination_folder = os.path.join(target, os.path.relpath(root, start=BUILD_DIR))
                os.makedirs(destination_folder, exist_ok=True)
                shutil.copy(filepath, destination_folder)
                counter += 1
    print(f"{counter} build files")


def folders_to_zip(source: str, target: str, df: pd.DataFrame):
    """
    Compress each folder in a directory to a zip archive and updated the 'Archived' flag in the dataframe
    :param source: Directory containing folders to be zipped
    :param target: Directory to save zip files
    :param df: Dataframe
    """
    archives = [x for x in os.scandir(source) if x.is_dir()]
    for entry in archives:
        row_found = match_folder_to_row(entry.name, df)
        if row_found is None:
            continue
        zip_path = os.path.join(target, f"{entry.name}.zip")
        shutil.make_archive(zip_path[:-4], 'zip', entry.path)
        df.at[row_found.name, 'Archived'] = True


def is_archivable(repo_dir_name: str, df: pd.DataFrame) -> bool:
    """
    Check if the repo fulfills the requirements to be archived:
    - Can be matched to the repo database
    - Compilation output has produced executable files
    - Source repo is currently on disk
    :param repo_dir_name: Name of the directory where the repo source (or build) is stored
    :param df: Dataframe with all repo data
    :return: True or False
    """
    row_found = match_folder_to_row(repo_dir_name, df)
    if row_found is None:
        return False
    if pd.isna(row_found['Execs']) or row_found['Execs'] == '':
        print("No executables!")
        return False
    if not row_found['On_disk']:
        print("Source files not on disk!")
        return False
    return True


def process_repo(repo_dir: os.DirEntry, arch_dir: str):
    try:
        copy_source_files(repo_dir.name, arch_dir)
        copy_build_files(repo_dir.name, arch_dir)
    # TODO this happens with symbolic links, need to look into it
    except FileNotFoundError as e:
        print(e)
        # clean up the archival directory for this repo if it was already created
        try:
            shutil.rmtree(os.path.join(arch_dir, repo_dir.name))
            print("Archive directory cleaned up")
        except FileNotFoundError:
            pass
            print("No archive directory was created")


def main():
    df, _ = initialize()
    arch_dir = os.path.join('out', 'archive')
    zip_dir = os.path.join('out', 'zip')

    os.makedirs(arch_dir, exist_ok=True)
    os.makedirs(zip_dir, exist_ok=True)

    repos = [x for x in os.scandir(BUILD_DIR) if x.is_dir()]
    for entry in tqdm(repos):
        print()
        print(f"Processing {entry.name}...")
        if is_archivable(entry.name, df):
            process_repo(entry, arch_dir)

    # TODO fails when there are no execs because out/archive doesn't exist
    folders_to_zip(arch_dir, zip_dir, df)
    wrapup(data=df)


if __name__ == "__main__":
    main()
