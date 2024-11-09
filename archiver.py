import os
import shutil

from dotenv import load_dotenv
import pandas as pd

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
            if os.access(filepath, os.X_OK) or filename.lower().endswith('.exe'):
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
        df.at[row_found.index, 'Archived'] = True


def match_folder_to_row(folder_name: str, df: pd.DataFrame) -> pd.Series | None:
    row_copy = df.query(f"Folder == '{folder_name}'").copy()
    if len(row_copy) == 0:
        print(f"Folder '{folder_name}' not found in DataFrame")
        return None
    if len(row_copy) > 1:
        print(f"Folder '{folder_name}' appears in DataFrame multiple times")
        return None
    # exactly one match found
    return row_copy.iloc[[0]]


if __name__ == "__main__":
    df, _ = db_handler.initialize()
    arch_dir = os.path.join('out', 'archive')
    zip_dir = os.path.join('out', 'zip')

    repos = [x for x in os.scandir(BUILD_DIR) if x.is_dir()]
    for entry in repos:
        print()
        row_found = match_folder_to_row(entry.name, df)
        if row_found is None:
            continue
        if row_found['Execs'] == '' or pd.isna(row_found['Execs']):
            print(f"Build '{entry.name}' contains no executables")
            continue
        print(f"Archiving {entry.name}...")
        copy_source_files(entry.name, arch_dir)
        copy_build_files(entry.name, arch_dir)

    folders_to_zip(arch_dir, zip_dir, df)
    db_handler.wrapup(df)
