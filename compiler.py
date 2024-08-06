import subprocess
import os
import argparse
import shutil
from dotenv import load_dotenv

load_dotenv()

# get directory paths and replace path separators with ones used by the system
SOURCE_DIR = os.path.join(*os.getenv('SOURCE_DIR').split('/'))
OUT_DIR = os.path.join(*os.getenv('COMPILE_DIR').split('/'))


def do_compile(path: str):
    """
    :param path: Directory where Makefile is located
    """
    # run Makefile
    subprocess.run(['make', 'V=1'], cwd=path)


def save_dir_structure(path: str, fname: str):
    """
    List paths of all files and dirs contained in a root directory
    Save the output in a file
    """
    with open(fname, 'w') as f:
        for root, dirs, files in os.walk(path):
            for name in dirs:
                f.write(os.path.join(root, name) + '\n')
            for name in files:
                f.write(os.path.join(root, name) + '\n')


def compare_dir_structure(before_file: str, after_file: str) -> list[str]:
    """
    Given two files (before and after changes), list new paths that were added
    """
    with open(before_file, 'r') as f:
        before = set(f.read().splitlines())
    with open(after_file, 'r') as f:
        after = set(f.read().splitlines())
    return list(after - before)


def move_compiled_files(compiled_paths: list[str]):
    for item_path in compiled_paths:
        if os.path.isfile(item_path):
            new_path = item_path.replace(SOURCE_DIR, OUT_DIR, 1)
            shutil.move(item_path, new_path)
            print(f'New: {new_path}')


def clean_up(files_to_rm: list[str]):
    """
    Remove files with listed filepaths
    """
    for f in files_to_rm:
        os.remove(f)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('dirpath')
    args = parser.parse_args()
    repo_path = os.path.join(SOURCE_DIR, args.dirpath)
    
    before = 'before.txt'
    after = 'after.txt'
    
    save_dir_structure(repo_path, before)
    do_compile(repo_path)
    save_dir_structure(repo_path, after)
    
    diff = compare_dir_structure(before, after)
    move_compiled_files(diff)
    clean_up([before, after])


if __name__ == "__main__":
    main()
