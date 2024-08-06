import subprocess
import os
import argparse

MAIN_DIR = 'scraped_code'


def do_compile(path: str):
    """
    :param path: Directory where Makefile is located
    """
    # run makefile
    subprocess.run(['make', 'V=1'], cwd=path, capture_output=True)

    # print(f"Command exited with code {result.returncode}")


def save_dir_structure(path: str, fname: str):
    with open(fname, 'w') as f:
        for root, dirs, files in os.walk(path):
            for name in dirs:
                f.write(os.path.join(root, name) + '\n')
            for name in files:
                f.write(os.path.join(root, name) + '\n')


def compare_dir_structure(before_file: str, after_file: str) -> list():
    with open(before_file, 'r') as f:
        before = set(f.read().splitlines())
    with open(after_file, 'r') as f:
        after = set(f.read().splitlines())
    return list(after - before)


"""
def find_executable_paths(path: str) -> list[str]:
    executable_files: list[str] = []

    for root, _, files in os.walk(path):
        for file in files:
            full_path: str = os.path.join(root, file)
            # check that file is readable and executable
            if os.access(full_path, os.R_OK | os.X_OK):
                executable_files.append(full_path)

    return executable_files
"""


def clean_up(files_to_rm: list):
    for f in files_to_rm:
        os.remove(f)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('dirpath')
    args = parser.parse_args()
    repo_path = os.path.join(MAIN_DIR, args.dirpath)
    
    before = 'before.txt'
    after = 'after.txt'
    
    save_dir_structure(repo_path, before)
    do_compile(repo_path)
    save_dir_structure(repo_path, after)
    
    diff = compare_dir_structure(before, after)
    with open(os.path.join(repo_path, 'aen_debug_diff.txt'), 'w') as f:
        for item in diff:
            f.write(item + '\n')
            print(item)
    
    clean_up([before, after])


if __name__ == "__main__":
    main()
