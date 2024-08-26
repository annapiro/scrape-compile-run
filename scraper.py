import requests
import os
import random
import time
import zipfile
import glob
from github import Github, Repository
from dotenv import load_dotenv
from datetime import date

load_dotenv()

TOKEN = os.getenv('API_KEY')
HEADERS = {'Authorization': f'token {TOKEN}'}
BASE_ENDPOINT = 'https://api.github.com'
SAVE_DIR = os.path.join(*os.getenv('SOURCE_DIR').split('/'))
SIZE_LIMIT = float(os.getenv('SIZE_LIMIT'))  # size limit for downloading repos in KB
DOWNLOAD_COUNT = 0


def get_random_repo(debug: str = None) -> Repository:
    """
    TODO
    """
    url = f'{BASE_ENDPOINT}/search/repositories'
    g = Github(TOKEN)

    if debug:
        return g.get_repo(debug)

    while True:
        query_params = {
            'q': f'language:c pushed:{get_formatted_date()}',
            'per_page': 100,
            'page': random.randint(1, 10)
        }
        response = requests.get(url, headers=HEADERS, params=query_params)
        response.raise_for_status()
        results = response.json()
        # get random repo from the selected page
        repo = g.get_repo(results['items'][random.randint(0, 99)]['full_name'])
        # output some query stats to the console
        print(f"\nFound {repo.full_name}")
        print(f"{query_params['q'].split()[1]}\tpage:{query_params['page']}\tsize:{repo.size/1024:.2f} MB")
        return repo


def is_eligible_repo(repo: Repository) -> bool:
    """
    Checks whether the repository matches eligibility criteria for download
    """
    # check if this repo has already been downloaded, by chance
    dircheck = os.path.join(SAVE_DIR, repo.full_name.replace('/', '-'))
    if glob.glob(dircheck + '*'):
        print("Repo already exists!")
        return False
    # limit by total size
    if SIZE_LIMIT != -1 and repo.size > SIZE_LIMIT:
        print("Size limit exceeded!")
        return False
    # don't include whatever calls itself a 'library'
    if 'library' in str(repo.description.lower()):
        print("May be a library!")
        return False
    # check that it contains at least one .c file
    response = requests.get(f'{BASE_ENDPOINT}/search/code',
                            headers=HEADERS,
                            params={'q': f'repo:{repo.full_name} extension:c'})
    if response.json()['total_count'] == 0:
        print("Contains no .c files!")
        return False

    return True


def get_formatted_date() -> str:
    """
    Convert randomly generated date to a format suitable for GitHub search queries
    """
    y, m = get_random_date()
    return f'{y}-{m:02}'


def get_random_date() -> (int, int):
    """
    Return a tuple with randomly chosen year and month
    Range between January 10 years ago and current year & month
    """
    current_year = date.today().year
    current_month = date.today().month
    # lower boundary: 10 years ago, converted to months
    range_from = (current_year - 10) * 12
    # upper boundary: current month
    range_to = (current_year * 12) + (current_month - 1)
    rand_month = random.randint(range_from, range_to)
    return rand_month // 12, (rand_month % 12 + 1)


def download_repo(full_name: str):
    """
    TODO
    """
    global DOWNLOAD_COUNT

    # get latest release if it's available
    release = requests.get(f'{BASE_ENDPOINT}/repos/{full_name}/releases/latest', headers=HEADERS)
    if release.status_code == 200:
        release_json = release.json()
        dwnld_url = release_json['zipball_url']
        dwnld_type = release_json['tag_name']
    # if there's no release, just get current state of the main branch
    elif release.status_code == 404:
        dwnld_url = f'{BASE_ENDPOINT}/repos/{full_name}/zipball'
        dwnld_type = 'main'
    else:
        print(f'Not downloaded, status code {release.status_code}')
        return

    response = requests.get(dwnld_url, headers=HEADERS)
    response.raise_for_status()
    zip_path = os.path.join(SAVE_DIR, full_name.replace('/', '-') + '.zip')
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
    print(f'Downloaded {full_name} ({dwnld_type})')


def check_rate_limits():
    """
    Print the number of remaining requests
    """
    r = requests.get(f'{BASE_ENDPOINT}/rate_limit', headers=HEADERS).json()
    # print(f"\nRate limit status"
    #       f"\n{r['resources']['core']['remaining']}/{r['resources']['core']['limit']}\tcore"
    #       f"\n{r['resources']['search']['remaining']}/{r['resources']['search']['limit']}\t\tsearch"
    #       f"\n{r['resources']['code_search']['remaining']}/{r['resources']['code_search']['limit']}\t\tcode search")
    if r['resources']['search']['remaining'] < 2 or r['resources']['code_search']['remaining'] < 2:
        print("\nWaiting for 60s...")
        time.sleep(60)


def main():
    download_limit = int(os.getenv('TO_DOWNLOAD'))

    while DOWNLOAD_COUNT < download_limit:
        start_time = time.time()
        try:
            repo = get_random_repo()
            if is_eligible_repo(repo):
                download_repo(repo.full_name)
        except Exception as e:
            print(e)
        end_time = time.time()
        print(f'{round(end_time - start_time)}s')

        check_rate_limits()


if __name__ == "__main__":
    main()
