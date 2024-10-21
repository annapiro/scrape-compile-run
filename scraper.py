import csv
import datetime
import glob
import os
import random
import time
import zipfile

from dotenv import load_dotenv
from github import Github, Repository
import pandas as pd
import requests
from tqdm import tqdm

import db_handler

load_dotenv()

TOKEN = os.getenv('API_KEY')
SIZE_LIMIT = float(os.getenv('SIZE_LIMIT'))  # size limit for downloading repos in KB
SAVE_DIR = os.path.join(*os.getenv('SOURCE_DIR').split('/'))
LOG_DIR = os.path.join('out', 'logs')

BASE_ENDPOINT = 'https://api.github.com'
HEADERS = {'Authorization': f'token {TOKEN}'}
DOWNLOAD_COUNT = 0


# def download_random_repos(limit: int):
#     """
#     Find and download random repos one by one, up to the specified download limit
#     :param limit: how many repos to download
#     """
#     while DOWNLOAD_COUNT < limit:
#         start_time = time.time()
#         try:
#             repo = find_random_repo()
#             if is_eligible_repo(repo):
#                 download_by_repo_name(repo.full_name)
#         except Exception as e:
#             print(e)
#         end_time = time.time()
#         print(f"{round(end_time - start_time)}s")
#
#
# def find_random_repo(debug: str = None) -> Repository:
#     g = Github(TOKEN)
#
#     if debug:
#         return g.get_repo(debug)
#
#     while True:
#         query_params = {
#             'q': f"language:c pushed:{get_random_date()}",
#             'per_page': 100,
#             'page': random.randint(1, 10)
#         }
#         results = fetch_response(f"{BASE_ENDPOINT}/search/repositories", query_params).json()
#         # get random repo from the selected page
#         repo = g.get_repo(results['items'][random.randint(0, 99)]['full_name'])
#         # output some query stats to the console
#         print(f"\nFound {repo.full_name}")
#         print(f"{query_params['q'].split()[1]}\tpage:{query_params['page']}\tsize:{repo.size/1024:.2f} MB")
#         return repo
#
#
# def get_random_date() -> str:
#     """
#     Return a year and month in a range between January 10 years ago and current year & month
#     Output formatted as string suitable for GitHub search queries
#     """
#     current_year = datetime.date.today().year
#     current_month = datetime.date.today().month
#     # lower boundary: 10 years ago, converted to months
#     range_from = (current_year - 10) * 12
#     # upper boundary: current month
#     range_to = (current_year * 12) + (current_month - 1)
#     rand_month = random.randint(range_from, range_to)
#     y = rand_month // 12
#     m = (rand_month % 12 + 1)
#     return f"{y}-{m:02}"


def is_eligible_repo(repo: Repository, v: bool = True) -> bool:
    """
    Checks whether the repository matches eligibility criteria for download
    :param repo: Repository to be checked
    :param v: verbosity setting
    :return: True or False
    """
    def log(reason: str):
        os.makedirs(LOG_DIR, exist_ok=True)
        log_file = os.path.join(LOG_DIR, 'filtered_repos.csv')
        file_exists = os.path.isfile(log_file)

        with open(log_file, 'a', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            if not file_exists:
                writer.writerow(['Repo', 'Filter'])
            writer.writerow([repo.full_name, reason])

    # check if this repo has already been downloaded, by chance
    dircheck = os.path.join(SAVE_DIR, repo.full_name.replace('/', '-'))
    if glob.glob(dircheck + '*'):
        if v:
            print("Repo already exists!")
        log("duplicate")
        return False
    # limit by total size
    if SIZE_LIMIT != -1 and repo.size > SIZE_LIMIT:
        if v:
            print("Size limit exceeded!")
        log("size")
        return False
    # don't include whatever calls itself a 'library'
    if repo.description:    
        if 'library' in str(repo.description.lower()):
            if v:
                print("May be a library!")
            log("library")
            return False
    # check that it contains at least one .c file
    response = fetch_response(f"{BASE_ENDPOINT}/search/code", params={'q': f"repo:{repo.full_name} extension:c"}).json()
    if response['total_count'] == 0:
        if v:
            print("Contains no .c files!")
        log("no c file")
        return False

    return True


def download_by_repo_name(repo_name: str):
    global DOWNLOAD_COUNT

    # get latest release if it's available
    release = fetch_response(f"{BASE_ENDPOINT}/repos/{repo_name}/releases/latest")
    if release.status_code == 200:
        release_json = release.json()
        dwnld_url = release_json['zipball_url']
        dwnld_type = release_json['tag_name']
    # if there's no release, just get current state of the main branch
    elif release.status_code == 404:
        dwnld_url = f'{BASE_ENDPOINT}/repos/{repo_name}/zipball'
        dwnld_type = 'main'
    else:
        print(f'Not downloaded, status code {release.status_code}')
        return

    response = fetch_response(dwnld_url)
    zip_path = os.path.join(SAVE_DIR, repo_name.replace('/', '-') + '.zip')
    os.makedirs(os.path.dirname(zip_path), exist_ok=True)
    with open(zip_path, 'wb') as f:
        f.write(response.content)
    # open and extract the zip file
    try:
        with zipfile.ZipFile(zip_path, 'r') as f:
            f.extractall(SAVE_DIR)
    finally:
        os.remove(zip_path)
    DOWNLOAD_COUNT += 1
    print(f'Downloaded {repo_name} ({dwnld_type})')


def download_by_commit_hash(repo_name: str, commit: str):
    global DOWNLOAD_COUNT
    response = fetch_response(f"{BASE_ENDPOINT}/repos/{repo_name}/zipball/{commit}")
    zip_path = os.path.join(SAVE_DIR, '-'.join(repo_name.replace('/', '-'), commit) + '.zip')
    os.makedirs(os.path.dirname(zip_path), exist_ok=True)
    with open(zip_path, 'wb') as f:
        f.write(response.content)
    # open and extract the zip file
    try:
        with zipfile.ZipFile(zip_path, 'r') as f:
            f.extractall(SAVE_DIR)
    finally:
        os.remove(zip_path)
    DOWNLOAD_COUNT += 1
    print(f"Downloaded {repo_name} ({commit})")


# def check_rate_limits():
#     """
#     If rate limits are low, time out
#     """
#     r = requests.get(f'{BASE_ENDPOINT}/rate_limit', headers=HEADERS).json()
#     if r['resources']['search']['remaining'] < 2 or r['resources']['code_search']['remaining'] < 2:
#         print("Waiting for 60s...\n")
#         time.sleep(60)


def scrape_whole_month(df: pd.DataFrame, month: str):
    g = Github(TOKEN)

    page = 1
    start = time.time()
    while True:
        query_params = {
            'q': f"language:c pushed:{month}",
            'per_page': 100,
            'page': page,
        }
        print(f"Query: {query_params}")
        try:
            response = fetch_response(f"{BASE_ENDPOINT}/search/repositories", params=query_params)
            results = response.json()
        except Exception as e:
            print(f"Error during GitHub search: {e}")
            page += 1
            continue
        for item in tqdm(results['items']):
            repo_name = item['full_name']
            if repo_name in df['Repo']:
                print(f"{repo_name} is a duplicate!")
                continue
            try:
                repo = g.get_repo(repo_name)
                if is_eligible_repo(repo):
                    languages = fetch_response(repo.languages_url).json()
                    commit_hash = get_latest_release_hash(repo_name)
                    df.loc[len(df)] = {'Repo': repo_name,
                                       'Commit': commit_hash,
                                       'Pushed': month,
                                       'Size': repo.size,
                                       'Stars': repo.stargazers_count,
                                       'Langs': languages,
                                       'C_ratio': get_c_ratio(languages),
                                       'Folder': '-'.join([repo_name.replace('/', '-'), commit_hash]),
                                       'On_disk': False,
                                       'Archived': False,
                                       }
            except Exception as e:
                print(f"Error processing repo {repo_name}: {e}")
                continue

        # break the loop if there are no more pages
        if 'Link' not in response.headers or 'rel="next"' not in response.headers['Link']:
            break
        page += 1

    minutes, seconds = divmod(int(time.time() - start), 60)
    print(f"Finished {month} in {minutes}m {seconds}s")


def get_next_month(months: list[str], from_date: datetime = None) -> str:
    """
    Get the latest month that is not in months
    :param months: set of months to ignore, each month must be in format 'yyyy-mm'
    :param from_date: if provided, only months earlier will be considered, if not provided uses previous month
    :return: latest month that is not found in months in format 'yyyy-mm'
    """

    def format_month(m: int) -> str:
        return f"{m // 12:04}-{m % 12 + 1:02}"

    dt = datetime.datetime.now() if from_date is None else from_date
    # month is zero-based: 0 is 01-0000, 12 is 01-0001 and so on
    month = (dt.month - 1 + dt.year * 12) - 1  # subtract 1 because we're ignoring current month

    while format_month(month) in months:
        assert month > 0, "Looking too far into the past"
        month -= 1

    return format_month(month)


def get_c_ratio(languages: dict) -> float:
    return languages.get("C", 0.0) / sum(languages.values())


def get_latest_release_hash(repo_name: str) -> str:
    # get latest release if it's available
    release = fetch_response(f"{BASE_ENDPOINT}/repos/{repo_name}/releases/latest", raise_for_status=False)
    if release.status_code == 200:
        tag_name = release.json()['tag_name']
        # https://docs.github.com/en/rest/git/refs?apiVersion=2022-11-28#get-a-reference
        tag = fetch_response(f"{BASE_ENDPOINT}/repos/{repo_name}/git/ref/tags/{tag_name}").json()
        # for some reason tag sometimes directly contains the commit sha and sometimes only the tag sha (?)
        sha_type = tag['object']['type']
        if sha_type == 'tag':
            tag_sha = tag['object']['sha']
            # https://docs.github.com/en/rest/git/tags?apiVersion=2022-11-28#get-a-tag
            tag2 = fetch_response(f"{BASE_ENDPOINT}/repos/{repo_name}/git/tags/{tag_sha}").json()
            commit_sha = tag2['object']['sha']
        elif sha_type == 'commit':
            commit_sha = tag['object']['sha']
        else:
            raise Exception(f"{repo_name} {tag_name} returned a '{sha_type}' object instead of tag or commit (??)")
        return commit_sha[:7]
    # if there's no release, just get current state of the main branch
    elif release.status_code == 404:
        repo = fetch_response(f"{BASE_ENDPOINT}/repos/{repo_name}").json()
        main_name = repo['default_branch']
        branch = fetch_response(f"{BASE_ENDPOINT}/repos/{repo_name}/branches/{main_name}").json()
        commit_sha = branch['commit']['sha']
        return commit_sha[:7]
    else:
        print(f"No release identified, status code {release.status_code}")
        return None


def fetch_response(url: str, params: dict = None, raise_for_status: bool = True) -> requests.Response:
    default_delay = 5
    while default_delay <= 120:
        response = requests.get(url, headers=HEADERS, params=params)

        # Too Many Requests / Forbidden
        if response.status_code in [429, 403]:
            if "retry-after" in response.headers:
                delay = int(response.headers["retry-after"])
            elif response.headers.get("x-ratelimit-remaining", None) == "0" and "x-ratelimit-reset" in response.headers:
                delay = (int(response.headers["x-ratelimit-reset"]) -
                         int(datetime.datetime.now(tz=datetime.UTC).timestamp()))
                # delay can be negative, if the reset date is in the past due to network latency
                if delay <= 0:
                    # do not sleep, retry immediately
                    continue
            else:
                delay = default_delay
                default_delay *= 2

            assert delay < 600, "delay too long"

            print(f"Waiting for {delay}s...")
            time.sleep(delay)
            continue

        if raise_for_status:
            response.raise_for_status()

        return response


if __name__ == "__main__":
    # download_random_repos(int(os.getenv('TO_DOWNLOAD')))

    df, months = db_handler.initialize()
    next_month = get_next_month(months)
    scrape_whole_month(df, next_month)
    months.append(next_month)
    db_handler.wrapup(df, months)
