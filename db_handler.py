import json
import os

import pandas as pd

from dotenv import load_dotenv

load_dotenv()

DATA_DIR = 'data'
DF_FILE = os.path.join(DATA_DIR, 'data.pkl')
MONTHS_FILE = os.path.join(DATA_DIR, 'months_tracker.json')


def initialize() -> (pd.DataFrame, list[str]):
    if os.path.isfile(DF_FILE):
        data = load_database()
    else:
        col_names = ['Repo', 'Commit', 'Pushed', 'Size', 'Stars', 'Languages', 'C percentage',
                     'On disk', 'Archived', 'Last compilation',
                     'Process', 'stdout', 'stderr', 'Build files', 'Executables']
        data = pd.DataFrame(columns=col_names)
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
