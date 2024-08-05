import subprocess
import os
import argparse

MAIN_DIR = 'scraped_code'
# MAKE_PATH = r'C:\Program Files (x86)\GnuWin32\bin\make.exe'
# os.environ['PATH'] += ';C:\\MinGW\\bin'
# os.environ['PATH'] += ';C:\Program Files (x86)\GnuWin32\bin'


def compile_and_get_executable_paths(path: str) -> list[str]:
    """
    :param path: Directory where Makefile is located
    """
    # run makefile
    subprocess.run('make', cwd=path, check=True)

    # print(f"Command exited with code {result.returncode}")

    executable_files: list[str] = []

    for root, _, files in os.walk(path):
        for file in files:
            full_path: str = os.path.join(root, file)
            # check that file is readable and executable
            if os.access(full_path, os.R_OK | os.X_OK):
                executable_files.append(full_path)

    return executable_files


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("dirpath")
    args = parser.parse_args()
    test_repo_dir = args.dirpath
    compile_path = os.path.join(MAIN_DIR, test_repo_dir)
    print(compile_and_get_executable_paths(compile_path))
