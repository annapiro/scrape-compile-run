import csv
import datetime
import glob
import os
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
            print("\nRepo already downloaded!")
        log("duplicate")
        return False
    # limit by total size
    if SIZE_LIMIT != -1 and repo.size > SIZE_LIMIT:
        if v:
            print("\nSize limit exceeded!")
        log("size")
        return False
    # don't include whatever calls itself a 'library'
    if repo.description:    
        if 'library' in str(repo.description.lower()):
            if v:
                print("\nMay be a library!")
            log("library")
            return False
    # check that it contains at least one .c file
    response = fetch_response(f"{BASE_ENDPOINT}/search/code", params={'q': f"repo:{repo.full_name} extension:c"}).json()
    if response['total_count'] == 0:
        if v:
            print("\nContains no .c files!")
        log("no c file")
        return False

    return True


def download_repo(repo_name: str, commit: str = None) -> str | None:
    """
    Download either latest available release of a repo or a specified commit state
    :param repo_name: Full name of the repo in the format 'owner/repo'
    :param commit: Commit hash (optional)
    :return: Name of the folder containing repo files or None if not downloaded
    """
    global DOWNLOAD_COUNT
    repo_name = repo_name.lower()

    if commit:
        dwnld_url = f"{BASE_ENDPOINT}/repos/{repo_name}/zipball/{commit}"
        dwnld_type = commit
    else:
        # get latest release if it's available
        release = fetch_response(f"{BASE_ENDPOINT}/repos/{repo_name}/releases/latest")
        if release.status_code == 200:
            release_json = release.json()
            dwnld_url = release_json['zipball_url']
            dwnld_type = release_json['tag_name']
        # if there's no release, just get current state of the main branch
        elif release.status_code == 404:
            dwnld_url = f"{BASE_ENDPOINT}/repos/{repo_name}/zipball"
            dwnld_type = 'main'
        else:
            print(f"\nNot downloaded, status code {release.status_code}")
            return

    response = fetch_response(dwnld_url)
    zip_path = os.path.join(SAVE_DIR, repo_name.replace('/', '-') + '.zip')
    os.makedirs(os.path.dirname(zip_path), exist_ok=True)
    with open(zip_path, 'wb') as f:
        f.write(response.content)
    try:
        with zipfile.ZipFile(zip_path, 'r') as f:
            # get the folder name from inside the zip
            # it should be the prefix of the first item on the list
            folder_name = f.namelist()[0].split('/')[0]
            # extract the zip file
            f.extractall(SAVE_DIR)
    finally:
        os.remove(zip_path)
    DOWNLOAD_COUNT += 1
    print(f"\nDownloaded {repo_name} ({dwnld_type}): {folder_name}")
    return folder_name


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
            print(f"\nError during GitHub search: {e}")
            page += 1
            continue
        for item in tqdm(results['items']):
            repo_name = item['full_name']
            if repo_name.lower() in df.index:
                print(f"\n{repo_name} is a duplicate!")
                continue
            try:
                repo = g.get_repo(repo_name)
                if is_eligible_repo(repo):
                    languages = fetch_response(repo.languages_url).json()
                    commit_hash = get_latest_release_hash(repo_name)
                    new_row = pd.DataFrame({
                        'Commit': commit_hash,
                        'Pushed': month,
                        'Size': repo.size,
                        'Stars': repo.stargazers_count,
                        'Langs': languages,
                        'C_ratio': get_c_ratio(languages),
                        'Folder': '-'.join([repo_name.replace('/', '-'), commit_hash]),
                        'On_disk': False,
                        'Archived': False,
                    }, index=[repo_name.lower()])

                    df = pd.concat([df, new_row])
            except Exception as e:
                print(f"\nError processing repo {repo_name}: {e}")
                continue

        # break the loop if there are no more pages
        if 'Link' not in response.headers or 'rel="next"' not in response.headers['Link']:
            break
        page += 1

    minutes, seconds = divmod(int(time.time() - start), 60)
    print(f"\nFinished {month} in {minutes}m {seconds}s")


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


def get_latest_release_hash(repo_name: str) -> str | None:
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

            assert delay < 600, "Delay too long"

            print(f"\nWaiting for {delay}s...")
            time.sleep(delay)
            continue

        if raise_for_status:
            response.raise_for_status()

        return response


if __name__ == "__main__":
    df, months = db_handler.initialize()
    next_month = get_next_month(months)
    # scrape_whole_month(df, next_month)
    scrape_whole_month(df, '2024-03')
    months.append(next_month)
    db_handler.wrapup(df, months)
