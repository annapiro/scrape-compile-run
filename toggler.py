import argparse
import os
import shutil

from dotenv import load_dotenv
import pandas as pd

import db_handler
from scraper import download_repo

load_dotenv()
SOURCE_DIR = os.path.join(*os.getenv('SOURCE_DIR').split('/'))


def _download_to_disk(row: pd.Series) -> (str, bool):
    """
    Helper function that downloads a repo to the source directory, to be applied row-wise
    :param row: Dataframe row containing data about the repo
    :return: Tuple(str, bool) where str is the updated name of the folder where repo files are stored
    and bool is confirmation whether this folder exists on disk (expected True)
    """
    folder_path = os.path.join(SOURCE_DIR, row['Folder'])
    if os.path.exists(folder_path):
        shutil.rmtree(folder_path)
    # after the download is complete, factual folder name may differ from the expected one
    confirmed_folder_name = download_repo(row['Repo'], row['Commit'])
    folder_path = os.path.join(SOURCE_DIR, confirmed_folder_name)
    # return confirmation that the folder now exists
    return (confirmed_folder_name,
            os.path.exists(folder_path) and os.path.isdir(folder_path))


def _remove_from_disk(row: pd.Series) -> bool:
    """
    Helper functions that removes a repo from the source directory, to be applied row-wise
    :param row: Dataframe row containing data about the repo
    :return: Confirmation whether the repo folder exists (expected False)
    """
    folder_path = os.path.join(SOURCE_DIR, row['Folder'])
    if os.path.exists(folder_path):
        shutil.rmtree(folder_path)
    # return confirmation whether the folder exists (expected False)
    return os.path.exists(folder_path)


def _update_download_status(row: pd.Series) -> bool:
    """
    Helper function that checks whether a repo exists in the source directory, to be applied row-wise
    :param row: Dataframe row containing data about the repo
    :return: True or False whether the repo folder exists
    """
    folder_path = os.path.join(SOURCE_DIR, row['Folder'])
    return os.path.exists(folder_path) and os.path.isdir(folder_path)


def main(command: str, query: str = '', sample_size: int = None):
    df, _ = db_handler.initialize()

    # only download repos that aren't already on disk
    if command == 'download':
        if query:
            query += ' and '
        query += '~On_disk'
    # only remove repos that are on disk
    elif command == 'remove':
        if query:
            query += ' and '
        query += ' and On_disk'

    # create a subset of the dataframe according to the query
    sub_df = df.query(query, inplace=False) if query else df.copy()

    print(f"{len(sub_df.index)} rows matched the condition before sampling")

    if sample_size and sample_size <= len(sub_df):
        sub_df = sub_df.sample(n=sample_size)

    if command == 'download':
        results = sub_df.apply(_download_to_disk, axis=1, result_type = 'expand')
        results.columns = ['On_disk', 'Folder']
        # filter only those rows that had a successful output
        filtered_results = results[(results['On_disk'] == True) &
                                   (results['Folder'].notna()) &
                                   (results['Folder'] != '')]
        # update those rows in the original dataframe
        df.loc[filtered_results.index, ['On_disk', 'Folder']] = filtered_results[['On_disk', 'Folder']]
        print(f"Successfully downloaded {len(filtered_results)} repos.")
    elif command == 'remove':
        df['On_disk'] = sub_df.apply(_remove_from_disk, axis=1)
    elif command == 'update':
        df['On_disk'] = sub_df.apply(_update_download_status, axis=1)
    else:
        print("Invalid command. Please use 'download', 'remove' or 'update'.")

    db_handler.wrapup(df)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Toggle download status of items in the dataframe.')
    parser.add_argument('command', type=str, choices=['download', 'remove', 'update'], help='Command to execute')
    parser.add_argument('--q', type=str, help='Query to filter the dataframe (e.g., "Stars > 1000") (optional)')
    parser.add_argument('--size', type=int, help='Number of random repos to sample (optional)')

    args = parser.parse_args()

    main(args.command, args.q, args.size)
