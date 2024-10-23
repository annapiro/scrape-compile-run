import os
import shutil

from dotenv import load_dotenv
import pandas as pd

import db_handler

load_dotenv()
SOURCE_DIR = os.path.join(*os.getenv('SOURCE_DIR').split('/'))
BUILD_DIR = os.path.join(*os.getenv('COMPILE_DIR').split('/'))


def copy_source_files(source: str, target: str):
    for root, _, files in os.walk(source):
        for filename in files:
            file, ext = os.path.splitext(filename)
            if 'readme' in file.lower() or ext == '.c' or ext == '.h':
                filepath = os.path.join(root, filename)
                destination_folder = os.path.join(target, os.path.relpath(root, start=SOURCE_DIR))
                os.makedirs(destination_folder, exist_ok=True)
                shutil.copy(filepath, destination_folder)


def copy_build_files(source: str, target: str):
    for root, _, files in os.walk(source):
        for filename in files:
            filepath = os.path.join(root, filename)
            if os.access(filepath, os.X_OK) or filename.lower().endswith('.exe'):
                destination_folder = os.path.join(target, os.path.relpath(root, start=BUILD_DIR))
                os.makedirs(destination_folder, exist_ok=True)
                shutil.copy(filepath, destination_folder)


def folders_to_zip(source: str, target: str, df: pd.DataFrame):
    archives = [x for x in os.scandir(source) if x.is_dir()]
    for entry in archives:
        if entry.name not in df.index:
            print(f"Archive '{entry.name}' not found in DataFrame")
            continue
        zip_path = os.path.join(target, f"{entry.name}.zip")
        shutil.make_archive(zip_path[:-4], 'zip', entry.path)

        df.at[entry.name, 'Archived'] = True


if __name__ == "__main__":
    df, _ = db_handler.initialize()
    arch_dir = os.path.join('out', 'archive')
    zip_dir = os.path.join('out', 'zip')

    repos = [x for x in os.scandir(BUILD_DIR) if x.is_dir()]
    for entry in repos:
        if entry.name not in df.index:
            print(f"Build '{entry.name}' not found in DataFrame")
            continue
        copy_source_files(entry.name, arch_dir)
        copy_build_files(entry.name, arch_dir)

    folders_to_zip(arch_dir, zip_dir, df)
    db_handler.wrapup(df)
