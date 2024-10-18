import os
import shutil

from dotenv import load_dotenv
import pandas as pd

from scraper import download_by_commit_hash

load_dotenv()
SOURCE_DIR = os.path.join(*os.getenv('SOURCE_DIR').split('/'))


def download_to_disk(row: pd.Series):
    folder_path = os.path.join(SOURCE_DIR, row['Folder'])
    if os.path.exists(folder_path):
        shutil.rmtree(folder_path)
    download_by_commit_hash(row['Repo'], row['Commit'])
    return os.path.isdir(folder_path)


def remove_from_disk(row: pd.Series) -> bool:
    folder_path = os.path.join(SOURCE_DIR, row['Folder'])
    if os.path.exists(folder_path):
        shutil.rmtree(folder_path)
    return os.path.exists(folder_path)


def update_download_status(row: pd.Series) -> bool:
    folder_path = os.path.join(SOURCE_DIR, row['Folder'])
    return os.path.isdir(folder_path)
