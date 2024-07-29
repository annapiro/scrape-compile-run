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

DEBUG_file_counter = 0

# TODO filter out repos that have no .c files (fx only .h) - search/code


# !!! obsolete
def get_repos(top: int = 100, pages: int = 10):
    """
    Find and download top 100 repositories that contain C code
    """
    url = f'{BASE_ENDPOINT}/search/repositories?q=language:C'  # &sort=stars&order=asc
    # (only checks the first page)
    response = requests.get(url, headers=HEADERS, params={'per_page': 100})
    response.raise_for_status()
    # print remaining limit at the start
    check_rate(response, 'Repo search')
    results = response.json()
    repos = results['items'][:top]
    for repo in repos:
        repo_name = repo['full_name']
        get_code_files(repo_name, pages)
        print(f'Downloaded: {repo_name}')
    # when done making requests, print remaining limit
    check_rate(response, 'Repo search')


def get_random_repos(nr_repos: int):
    url = f'{BASE_ENDPOINT}/search/repositories'
    g = Github(TOKEN)

    repos = []

    while len(repos) < nr_repos:
        query_params = {
            'q': f'language:c pushed:{get_formatted_date()}',
            'per_page': 100,
            'page': random.randint(1, 10)
        }
        # print(query_params)
        response = requests.get(url, headers=HEADERS, params=query_params)
        response.raise_for_status()
        results = response.json()
        # get random repo from the selected page
        repo = g.get_repo(results['items'][random.randint(0, 99)]['full_name'])
        # output some query stats to the console
        print(f"{repo.full_name}\n"
              f"{query_params['q'].split()[1]}\tpage:{query_params['page']}\tsize:{repo.size/1024:.2f} MB")
        # filter out repos a bit - limit by total size and don't include whatever calls itself a 'library'
        if repo.size <= SIZE_LIMIT_KB and 'library' not in str(repo.description):
            repos.append(repo.full_name)
        # repos.append(results['items'][random.randint(0, 99)])
    if response:
        check_rate(response, 'Repo search')

    # repos = [repo['full_name'] for repo in repos]
    print(repos)  # debug
    for repo in repos:
        download_repo(repo)


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


def get_formatted_date() -> str:
    """
    Convert randomly generated date to a format suitable for GitHub search queries
    """
    y, m = get_random_date()
    return f'{y}-{m:02}'


def download_repo(full_name: str):
    """
    TODO rate limit check
    """
    global DEBUG_file_counter
    DEBUG_file_counter = 0

    start_time = time.time()

    g = Github(TOKEN)
    repo = g.get_repo(full_name)
    repo_contents = repo.get_contents('')
    tar_path = os.path.join(SAVE_DIR, full_name.replace('/', '.'))

    def download_files(contents: list):
        global DEBUG_file_counter

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
                        DEBUG_file_counter += 1
            except Exception as e:
                print(f'Error downloading file: {content.path}')
                print(e)

    # get latest release if it's available
    release = requests.get(f'{BASE_ENDPOINT}/repos/{full_name}/releases/latest')
    if release.status_code == 200:
        response = requests.get(release.json()['zipball_url'])
        response.raise_for_status()
        zip_path = f'{tar_path}.zip'
        os.makedirs(os.path.dirname(zip_path), exist_ok=True)
        with open(zip_path, 'wb') as f:
            f.write(response.content)
            DEBUG_file_counter += 1
        # open and extract the zip file
        with zipfile.ZipFile(zip_path, 'r') as f:
            f.extractall(tar_path)
    # if there's no release, just download files in main
    elif release.status_code == 404:
        download_files(repo_contents)
    else:
        print(f'Did not download {full_name}, status code {release.status_code}')
        return

    end_time = time.time()
    print(f'Downloaded {full_name}: {DEBUG_file_counter} files, {round(end_time - start_time)}s')


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


def download_file(url: str, save_path: str):
    """
    Download a single file given its raw url
    """
    response = requests.get(url)
    response.raise_for_status()
    # check_rate(response, "download file")
    with open(save_path, 'wb') as f:
        f.write(response.content)


def check_rate(response: requests.Response, note: str = "General"):
    """
    Print the number of remaining requests
    """
    rate_now = int(response.headers['x-ratelimit-remaining'])
    rate_max = int(response.headers['x-ratelimit-limit'])
    print(f"{note} requests left: {rate_now}/{rate_max}")


def main():
    # get_repos(top=2, pages=1)
    # get_random_repos(5)
    # exit()
    
    get_random_repos(20)


if __name__ == "__main__":
    main()
