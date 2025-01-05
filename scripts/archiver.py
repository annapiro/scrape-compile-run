import os
import shutil

from dotenv import load_dotenv
import pandas as pd
from tqdm import tqdm

from compiler import is_executable
import db_handler

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
    archives = [x for x in os.scandir(source) if x.is_dir()]
    for entry in archives:
        row_found = match_folder_to_row(entry.name, df)
        if row_found is None:
            continue
        zip_path = os.path.join(target, f"{entry.name}.zip")
        shutil.make_archive(zip_path[:-4], 'zip', entry.path)
        df.at[row_found.name, 'Archived'] = True


def match_folder_to_row(folder_name: str, df: pd.DataFrame) -> pd.Series | None:
    matches = df.query(f"Folder == '{folder_name}'").copy()
    if len(matches) == 0:
        print(f"Folder '{folder_name}' not found in DataFrame")
        return None
    if len(matches) > 1:
        print(f"Folder '{folder_name}' appears in DataFrame multiple times")
        return None
    # exactly one match found
    return matches.iloc[0]


if __name__ == "__main__":
    df, _ = db_handler.initialize()
    arch_dir = os.path.join('out', 'archive')
    zip_dir = os.path.join('out', 'zip')

    repos = [x for x in os.scandir(BUILD_DIR) if x.is_dir()]
    for entry in tqdm(repos):
        print()
        print(f"Processing {entry.name}...")
        row_found = match_folder_to_row(entry.name, df)
        if row_found is None:
            continue
        if row_found['Execs'] == '' or pd.isna(row_found['Execs']):
            print("No executables!")
            continue
        if not row_found['On_disk']:
            print("Source files not on disk!")
            continue
        try:
            copy_source_files(entry.name, arch_dir)
            copy_build_files(entry.name, arch_dir)
        # TODO this happens with symbolic links, need to look into it
        except FileNotFoundError as e:
            print(e)
            # clean up the archival directory for this repo if it was already created
            try:
                shutil.rmtree(os.path.join(arch_dir, entry.name))
                print("Archive directory cleaned up")
            except FileNotFoundError:
                pass
                print("No archive directory was created")

    # TODO fails when there are no execs because out/archive doesn't exist
    folders_to_zip(arch_dir, zip_dir, df)
    db_handler.wrapup(df)
