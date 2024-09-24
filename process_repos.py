import os
import pandas as pd
import json
import requests
import time
from datetime import datetime
from tqdm import tqdm
from dotenv import load_dotenv
from github import Github
from scraper import is_eligible_repo, check_rate_limits

load_dotenv()

TOKEN = os.getenv('API_KEY')
HEADERS = {'Authorization': f"token {TOKEN}"}
BASE_ENDPOINT = 'https://api.github.com'
DATA_DIR = 'data'
DF_FILE = os.path.join(DATA_DIR, 'data.pkl')
MONTHS_FILE = os.path.join(DATA_DIR, 'months_tracker.json')


def initialize() -> (pd.DataFrame, list[str]):
    if os.path.isfile(DF_FILE):
        data = load_database()
    else:
        col_names = ['Repo', 'Commit', 'Pushed', 'Size', 'On disk',
                     'CMakeLists', 'Makefiles', 'C files',
                     'Last compilation', 'stdout', 'stderr', 'Output files']
        data = pd.DataFrame(columns=col_names)
    if os.path.isfile(MONTHS_FILE):
        months = load_months_tracker()
    else:
        months = []
    return data, months


def wrapup(data: pd.DataFrame, months: list[str]):
    os.makedirs(DATA_DIR, exist_ok=True)
    update_database(data)
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


def get_month(months: list[str], from_date: datetime = None) -> str:
    """
    Get the latest month that is not in months
    :param months: set of months to ignore, each month must be in format 'yyyy-mm'
    :param from_date: if provided, only months earlier will be considered, if not provided uses previous month
    :return: latest month that is not found in months in format 'yyyy-mm'
    """

    def format_month(m: int) -> str:
        return f"{m // 12:04}-{m % 12 + 1:02}"

    dt = datetime.now() if from_date is None else from_date
    # month is zero-based: 0 is 01-0000, 12 is 01-0001 and so on
    month = (dt.month - 1 + dt.year * 12) - 1  # subtract 1 because we're ignoring current month

    while format_month(month) in months:
        assert month > 0, "Looking too far into the past"
        month -= 1

    return format_month(month)


def get_latest_release_hash(repo_name: str) -> str:
    # get latest release if it's available
    release = requests.get(f"{BASE_ENDPOINT}/repos/{repo_name}/releases/latest", headers=HEADERS)
    if release.status_code == 200:
        tag_name = release.json()['tag_name']
        # https://docs.github.com/en/rest/git/refs?apiVersion=2022-11-28#get-a-reference
        tag = fetch_json(f"{BASE_ENDPOINT}/repos/{repo_name}/git/ref/tags/{tag_name}")
        # for some reason tag sometimes directly contains the commit sha and sometimes only the tag sha (?)
        sha_type = tag['object']['type']
        if sha_type == 'tag':
            tag_sha = tag['object']['sha']
            # https://docs.github.com/en/rest/git/tags?apiVersion=2022-11-28#get-a-tag
            tag2 = fetch_json(f"{BASE_ENDPOINT}/repos/{repo_name}/git/tags/{tag_sha}")
            commit_sha = tag2['object']['sha']
        elif sha_type == 'commit':
            commit_sha = tag['object']['sha']
        else:
            raise Exception(f"{repo_name} {tag_name} returned a '{sha_type}' object instead of tag or commit (??)")
        return commit_sha[:7]
    # if there's no release, just get current state of the main branch
    elif release.status_code == 404:
        repo = fetch_json(f"{BASE_ENDPOINT}/repos/{repo_name}")
        main_name = repo['default_branch']
        branch = fetch_json(f"{BASE_ENDPOINT}/repos/{repo_name}/branches/{main_name}")
        commit_sha = branch['commit']['sha']
        return commit_sha[:7]
    else:
        print(f"No release identified, status code {release.status_code}")
        return None


def fetch_json(url: str) -> dict:
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    df, processed_months = initialize()

    url = f"{BASE_ENDPOINT}/search/repositories"
    g = Github(TOKEN)

    # TODO later download zip based on commit hash:
    # https://docs.github.com/en/rest/repos/contents?apiVersion=2022-11-28#download-a-repository-archive-tar

    # update the dataframe with repos from the next eligible month
    month = get_month(processed_months)
    page = 1
    start = time.time()
    while True:
        query_params = {
            'q': f"language:c pushed:{month}",
            'per_page': 100,
            'page': page,
        }
        try:
            response = requests.get(url, headers=HEADERS, params=query_params)
            response.raise_for_status()
            results = response.json()
        except Exception as e:
            print(f"Error during GitHub search: {e}")
            print(f"Query: {query_params}")
            page += 1
            continue
        for item in tqdm(results['items']):
            repo_name = item['full_name']
            if repo_name in df['Repo']:
                print(f"{repo_name} is a duplicate!")
                print(f"Query: {query_params}")
                continue
            try:
                repo = g.get_repo(repo_name)
                if is_eligible_repo(repo, v=False):
                    df.loc[len(df)] = {'Repo': repo_name,
                                       'Commit': get_latest_release_hash(repo_name),
                                       'Pushed': month,
                                       'Size': repo.size,
                                       'On disk': False,
                                       }
            except Exception as e:
                print(f"Error processing repo {repo_name}: {e}")
                continue
            check_rate_limits()

        # break the loop if there are no more pages
        if 'Link' not in response.headers or 'rel="next"' not in response.headers['Link']:
            break
        page += 1

    minutes, seconds = divmod(int(time.time() - start), 60)
    print(f"Finished {month} in {minutes}m{seconds}s")
    processed_months.append(month)
    wrapup(df, processed_months)
    print("Data files updated.")
