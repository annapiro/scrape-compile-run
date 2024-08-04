import requests
import os
import random
import time
import zipfile
from github import Github
from dotenv import load_dotenv
from datetime import date

load_dotenv()

TOKEN = os.getenv('API_KEY')
HEADERS = {'Authorization': f'token {TOKEN}'}
BASE_ENDPOINT = 'https://api.github.com'
SAVE_DIR = 'scraped_code'
SIZE_LIMIT_KB = 20480
DOWNLOAD_COUNT = 0

# TODO filter out repos that have no .c files (fx only .h) - search/code


def get_random_repo() -> str:
    """
    TODO
    """
    url = f'{BASE_ENDPOINT}/search/repositories'
    g = Github(TOKEN)  # TODO it's literally only used for one line of code

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
        # limit by total size
        if repo.size > SIZE_LIMIT_KB:
            print("Size limit exceeded!")
            continue
        # don't include whatever calls itself a 'library'
        if 'library' in str(repo.description):
            print("May be a library!")
            continue
        return repo.full_name


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
    start_time = time.time()

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
    with open(zip_path, 'wb') as f:
        f.write(response.content)
    # open and extract the zip file
    with zipfile.ZipFile(zip_path, 'r') as f:
        f.extractall(SAVE_DIR)

    end_time = time.time()
    DOWNLOAD_COUNT += 1
    print(f'Downloaded {full_name} ({dwnld_type}) in {round(end_time - start_time)}s')


# obsolete functions
'''
def get_code_files(repo_name: str, pages: int = 10):
    """
    Get links to the actual code files
    """
    url = f"{BASE_ENDPOINT}/search/code?q=language:C&repo={repo_name}"
    page = 1
    files = list()
    response = None
    while page <= pages:
        response = requests.get(url, headers=HEADERS, params={'per_page': 100, 'page': page})
        response.raise_for_status()
        data = response.json()
        items = data.get('items', [])  # default to empty list
        if not items:
            break
        files += items
        page += 1
    # print remaining limit after code search done
    check_rate(response, "Code search")

    # download raw files
    file_response = None
    for f in files:
        file_url = f['url']
        file_name = os.path.basename(f['path'])
        save_path = f'scraped_code/{repo_name}/{file_name}'
        file_response = requests.get(file_url, headers=HEADERS)
        file_response.raise_for_status()
        download_url = file_response.json()['download_url']
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        download_file(download_url, save_path)
    # print remaining limit for other requests
    check_rate(file_response)


def download_files(contents: list):
    for content in contents:
        try:
            if content.type == 'dir':
                download_files(repo.get_contents(content.path))
            # filter for C-related files
            elif content.name.endswith('.c') or content.name.endswith('.h') or content.name in ['Makefile', 'CMakeLists.txt']:
                file_content = repo.get_contents(content.path).decoded_content
                file_path = os.path.join(tar_path, content.path)
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                with open(file_path, 'wb') as f:
                    f.write(file_content)
        except Exception as e:
            print(f'Error downloading file: {content.path}')
            print(e)
'''


def check_rate_limits():
    """
    Print the number of remaining requests
    """
    r = requests.get(f'{BASE_ENDPOINT}/rate_limit', headers=HEADERS).json()
    print(f"\nRate limit status"
          f"\n{r['resources']['core']['remaining']}/{r['resources']['core']['limit']}\tcore"
          f"\n{r['resources']['search']['remaining']}/{r['resources']['search']['limit']}\t\tsearch"
          f"\n{r['resources']['code_search']['remaining']}/{r['resources']['code_search']['limit']}\t\tcode search")


def main():
    download_limit = 5
    while DOWNLOAD_COUNT < download_limit:
        random_repo = get_random_repo()
        download_repo(random_repo)
        check_rate_limits()
    # clean up zip files
    for z in [f for f in os.listdir(SAVE_DIR) if f.endswith('zip')]:
        os.remove(os.path.join(SAVE_DIR, z))


if __name__ == "__main__":
    main()
