import argparse
import os
import shutil

from dotenv import load_dotenv
import pandas as pd

import db_handler
from scraper import download_by_commit_hash

load_dotenv()
SOURCE_DIR = os.path.join(*os.getenv('SOURCE_DIR').split('/'))


def download_to_disk(row: pd.Series) -> bool:
    folder_path = os.path.join(SOURCE_DIR, row['Folder'])
    if os.path.exists(folder_path):
        shutil.rmtree(folder_path)
    download_by_commit_hash(row['Repo'], row['Commit'])
    # return confirmation that the folder now exists
    return os.path.isdir(folder_path)


def remove_from_disk(row: pd.Series) -> bool:
    folder_path = os.path.join(SOURCE_DIR, row['Folder'])
    if os.path.exists(folder_path):
        shutil.rmtree(folder_path)
    # return confirmation whether the folder exists (expected False)
    return os.path.exists(folder_path)


def update_download_status(row: pd.Series) -> bool:
    folder_path = os.path.join(SOURCE_DIR, row['Folder'])
    return os.path.isdir(folder_path)


def main(command: str, condition: str, sample: int = None):
    df, _ = db_handler.initialize()

    if command == 'download':
        condition += ' and ~On_disk'
    elif command == 'remove':
        condition += ' and On_disk'

    filtered_df = df.query(condition, inplace=False)
    print(f"{len(filtered_df.index)} rows match the condition before sampling")

    if sample is not None and sample <= len(filtered_df):
        filtered_df = filtered_df.sample(n=sample)

    if command == 'download':
        df['On_disk'] = filtered_df.apply(download_to_disk, axis=1)
    elif command == 'remove':
        df['On_disk'] = filtered_df.apply(remove_from_disk, axis=1)
    elif command == 'update':
        df['On_disk'] = filtered_df.apply(update_download_status, axis=1)
    else:
        print("Invalid command. Please use 'download', 'remove' or 'update'.")

    db_handler.wrapup(df)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Toggle download status of items in the dataframe.')
    parser.add_argument('command', type=str, choices=['download', 'remove', 'update'], help='Command to run')
    parser.add_argument('condition', type=str, help='Condition to filter the dataframe (e.g., "Stars > 1000")')
    parser.add_argument('--sample', type=int, help='Number of random repos to sample (optional)')

    args = parser.parse_args()

    main(args.command, args.condition, args.sample_size)
