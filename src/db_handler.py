import json
import os

import pandas as pd

from dotenv import load_dotenv

load_dotenv()

DATA_DIR = 'data'
DF_FILE = os.path.join(DATA_DIR, 'data.pkl')
MONTHS_FILE = os.path.join(DATA_DIR, 'months_tracker.json')
os.makedirs(DATA_DIR, exist_ok=True)


class EmptyDatasetError(Exception):
    """
    Exception raised when the dataset is empty.
    """
    def __init__(self, msg="Dataset is empty! Run Scraper to populate it with data."):
        super().__init__(msg)


def initialize() -> (pd.DataFrame, list[str]):
    if os.path.isfile(DF_FILE):
        data = load_database()
    else:
        columns = {
            'Repo': 'string',
            'Commit': 'string',
            'Pushed': 'string',
            'Size': 'int32',
            'Stars': 'int32',
            'C_ratio': 'float32',
            'Langs': 'object',
            'Process': 'string',
            'Execs': 'string',
            'Last_comp': 'string',
            'Folder': 'string',
            'On_disk': 'bool',
            'Archived': 'bool',
        }

        data = pd.DataFrame({col: pd.Series(dtype=dtype) for col, dtype in columns.items()})
        data.set_index('Repo', inplace=True)

    if os.path.isfile(MONTHS_FILE):
        months = load_months_tracker()
    else:
        months = []
    return data, months


def wrapup(data: pd.DataFrame, months: list[str] = None):
    os.makedirs(DATA_DIR, exist_ok=True)
    update_database(data)
    if months:
        update_months_tracker(months)


def load_database():
    return pd.read_pickle(DF_FILE)


def update_database(data: pd.DataFrame):
    data.to_pickle(DF_FILE)


def load_months_tracker() -> list[str]:
    with open(MONTHS_FILE, 'rt', encoding="utf-8") as f:
        return json.load(f)


def update_months_tracker(months: list[str]):
    with open(MONTHS_FILE, 'wt', encoding="utf-8") as f:
        json.dump(months, f)


def load_blacklist() -> set:
    blacklist_path = os.path.join(DATA_DIR, 'blacklist.txt')
    if not os.path.isfile(blacklist_path):
        # create an empty blacklist file if it doesn't exist
        with open(blacklist_path, 'w') as f:
            pass
    with open(blacklist_path, 'r') as f:
        blacklist = {line.strip() for line in f if line.strip()}
    return blacklist


def match_folder_to_row(folder_name: str, df: pd.DataFrame) -> pd.Series | None:
    """
    Find row in the dataframe that corresponds to the given source folder
    :param folder_name: Folder to find in the dataframe
    :param df: Dataframe
    :return: pandas Series if found, otherwise None
    """
    matches = df.query(f"Folder == '{folder_name}'").copy()
    if len(matches) == 0:
        print(f"Folder '{folder_name}' not found in DataFrame")
        return None
    if len(matches) > 1:
        print(f"Folder '{folder_name}' appears in DataFrame multiple times")
        return None
    # exactly one match found
    return matches.iloc[0]
