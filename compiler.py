from datetime import datetime
import os
import shutil
import signal
import subprocess

from dotenv import load_dotenv
from tqdm import tqdm

import db_handler

load_dotenv()

# get directory paths and replace path separators with ones used by the system
SOURCE_DIR = os.path.join(*os.getenv('SOURCE_DIR').split('/'))
BUILD_DIR = os.path.join(*os.getenv('COMPILE_DIR').split('/'))
LOG_DIR = os.path.join('out', 'logs')


def run_cmake(cmake_path: str, repo_path: str) -> (str, str, str):
    """
    :param cmake_path: Path to the CMakeLists.txt file (relative to cwd)
    :param repo_path: Root directory of the repository (full path, relative to cwd)
    :return: executed command(s), list of target files, stdout, stderr
    """
    out_log = ''
    err_log = ''

    # create build folder if it doesn't exist
    build_rel = 'build'  # relative to the repo root
    build_path = os.path.join(repo_path, build_rel)
    os.makedirs(build_path, exist_ok=True)

    # remove file name from the CMakeLists path
    cmake_dir = os.path.dirname(cmake_path)

    # make the source path relative to the repo root
    source_rel = os.path.relpath(cmake_dir, start=repo_path)

    print(f"Run cmake: {cmake_dir}")
    command = ['cmake', '-S', source_rel, '-B', build_rel]
    returncode, out, err = run_subprocess(command, repo_path)

    # logging
    process_log = 'cmake'
    out_log += out
    err_log += err

    # TODO does it make sense to continue if return code is not 0? (generates additional string junk)

    # build
    command = ['cmake', '--build', build_rel]
    _, out, err = run_subprocess(command, repo_path)

    # logging
    process_log = 'cmake --build'
    if out_log:
        out_log += '\n\n'
    out_log += out
    if err_log:
        err_log += '\n\n'
    err_log += err

    return process_log, out_log, err_log


def run_make(make_path: str) -> (str, str, str):
    """
    :param make_path: Directory where Makefile is located or will be generated (full path, relative to cwd)
    :return: executed command(s), list of target files, stdout, stderr
    """
    print(f"Run make: {make_path}")
    command = ['make', 'V=1']
    _, out, err = run_subprocess(command, make_path)
    return command[0], out, err


def run_gcc(repo_path: str, cfiles: list) -> (str, str, str):
    """
    :param repo_path: Path to the repository root
    :param cfiles: List of paths to all .c files in the repo
    :return: executed command, list of target files, stdout, stderr
    """
    output_file = 'compiled_output'
    cfiles_relative = [os.path.relpath(f, repo_path) for f in cfiles]
    print(f"Run gcc: {repo_path}")
    command = ['gcc'] + cfiles_relative + ['-o', output_file]
    _, out, err = run_subprocess(command, repo_path)
    return command[0], out, err


def run_subprocess(command: list, cwd: str) -> (int, str, str):
    """
    :return: subprocess return code, stdout and stderr
    """
    process = subprocess.Popen(command,
                               cwd=cwd,
                               start_new_session=True,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,
                               text=True)

    try:
        stdout, stderr = process.communicate(timeout=180)
        return process.returncode, stdout, stderr
    except subprocess.TimeoutExpired as e:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)  # terminate the whole process group
        print("Timeout")
        # attempt to get any output after killing the process
        try:
            stdout, stderr = process.communicate(timeout=10)  # get any output after killing
        except subprocess.TimeoutExpired:
            stdout, stderr = None, "Timeout"
        return None, stdout, stderr
    except Exception as e:
        print(e)
        return None, None, str(e)


# TODO return dict instead + add .a and .so files
# TODO check traversal
def get_relevant_files(root_path: str) -> (list, list, list):
    makefiles = []
    cmakelists = []
    cfiles = []
    
    # print(f'Walk subdirs: {root_path}')
    # TODO stop checking for other types once a higher-priority type is found
    for root, _, files in os.walk(root_path):
        for f in files:
            if f.endswith('.c'):
                cfiles.append(os.path.join(root, f))
            elif f == 'Makefile':
                score = assign_priority_score(root, f)
                makefiles.append((os.path.join(root, f), *score))
            elif f == 'CMakeLists.txt':
                score = assign_priority_score(root, f)
                cmakelists.append((os.path.join(root, f), *score))
    return makefiles, cmakelists, cfiles


def assign_priority_score(root_path: str, file_path: str) -> (int, int):
    priority = 0
    keyword_priority = {
        'src': 2,
        'source': 2,
        'scripts': 1,
        'app': 1,
        'program': 1,
    }

    for keyword, level in keyword_priority.items():
        if keyword in file_path:
            priority = level
            break

    depth = abs(len(os.path.relpath(file_path, root_path).split(os.sep)) - 1)

    return priority, -depth


def find_best_file(file_list: list) -> str:
    file_list.sort(key=lambda x: (x[1], x[2]), reverse=True)
    return file_list[0][0]


def save_dir_structure(top: str, fname: str, recurse: bool = True):
    """
    List paths of all files and dirs contained in a root directory
    Save the output in a file
    """
    with open(fname, 'a', encoding='utf-8') as f:
        for root, dirs, files in os.walk(top):
            for name in files:
                f.write(os.path.join(root, name) + '\n')
            if not recurse:
                break


def compare_dir_structure(before_file: str, after_file: str) -> list[str]:
    """
    Given two files (before and after changes), list new paths that were added
    """
    with open(before_file, 'r', encoding='utf-8') as f:
        before = set(f.read().splitlines())
    with open(after_file, 'r', encoding='utf-8') as f:
        after = set(f.read().splitlines())
    return list(after - before)


def move_compiled_files(compiled_paths: list[str], repo_folder: str):
    for item_path in compiled_paths:
        if os.path.isfile(item_path):
            # file path relative to the repo folder
            stripped_path = strip_path(item_path, repo_folder)
            # new folder that the file will be moved to, relative to cwd
            new_folder = os.path.join(BUILD_DIR, repo_folder, os.path.dirname(stripped_path))
            os.makedirs(new_folder, exist_ok=True)
            # path directly to the file, relative to cwd
            new_file_path = os.path.join(BUILD_DIR, repo_folder, stripped_path)
            shutil.move(item_path, new_file_path)
            # only report new executables
            if is_executable(new_file_path):
                print(f"New: {new_file_path}")


def strip_path(file_path: str, repo_folder: str) -> str:
    """
    Remove source directory prefix or cwd prefix from a filepath
    :param file_path: Path to file with a prefix
    :param repo_folder: Name of the folder where the repo is saved ('owner-repo-123abc')
    :return: Path to file stripped of the prefix
    """
    cwd = os.getcwd()
    return os.path.relpath(file_path, start=cwd if file_path.startswith(cwd) else os.path.join(SOURCE_DIR, repo_folder))


def is_executable(filepath: str) -> bool:
    _, output, _ = run_subprocess(command=['file', filepath], cwd='.')
    output = output.strip('\n')
    # trim the file name from the output
    file_description = output.split(': ', 1)[1].lower()
    if 'executable' in file_description:
        if 'text executable' not in file_description:
            if 'CMakeFiles' not in filepath:
                return True
    return False


def clean_up(files_to_rm: list[str]):
    """
    Remove files with listed filepaths
    """
    for f in files_to_rm:
        os.remove(f)


def main():
    # repos = os.scandir(SOURCE_DIR)
    os.makedirs(LOG_DIR, exist_ok=True)
    df, _ = db_handler.initialize()

    # only iterate through the repos that are saved to disk
    filtered_df = df[df['On_disk']].copy()

    for index, row in tqdm(filtered_df.iterrows()):
        print(" " + index)
        repo_folder = row['Folder']  # only root directory
        repo_path = os.path.join(SOURCE_DIR, repo_folder)  # full path

        if not os.path.isdir(repo_path):
            print(f"{repo_path} not found on disk")
            df.at[index, 'On_disk'] = False
            continue

        tmp_dir = os.path.join('out', 'tmp')
        os.makedirs(tmp_dir, exist_ok=True)
        before = os.path.join(tmp_dir, 'before.txt')
        after = os.path.join(tmp_dir, 'after.txt')

        # record initial repository structure
        save_dir_structure(repo_path, before)
        # record cwd structure because sometimes files end up there
        save_dir_structure(os.getcwd(), before, recurse=False)

        # process, output, error
        result: list[str] = ['', '', '']

        # assuming there's Makefile or CMakeLists in root
        cmakelists_path = os.path.join(repo_path, 'CMakeLists.txt')
        makefile_path = os.path.join(repo_path, 'Makefile')

        if os.path.isfile(cmakelists_path):
            result = run_cmake(cmakelists_path, repo_path)
        elif os.path.isfile(makefile_path):
            result = run_make(repo_path)
        else:
            # walk the repo and find the next best option
            makefiles, cmakelists, cfiles = get_relevant_files(repo_path)
            if cmakelists:
                cmakelists_path = find_best_file(cmakelists)
                result = run_cmake(cmakelists_path, repo_path)
            elif makefiles:
                makefile_path = find_best_file(makefiles)
                makefile_dir = os.path.dirname(makefile_path)
                result = run_make(makefile_dir)
            elif cfiles:
                result = run_gcc(repo_path, cfiles)

        save_dir_structure(repo_path, after)
        save_dir_structure(os.getcwd(), after, recurse=False)
        # this will contain full paths
        diff = compare_dir_structure(before, after)

        df.at[index, 'Process'] = result[0] if result[0] else ''
        df.at[index, 'Out'] = result[1].strip('\n ') if result[1] else ''
        df.at[index, 'Err'] = result[2].strip('\n ') if result[2] else ''
        # only store relative paths (cwd or repo prefix stripped)
        df.at[index, 'New_files'] = '\n'.join([strip_path(f, repo_folder) for f in diff])
        df.at[index, 'Execs'] = '\n'.join([strip_path(f, repo_folder) for f in diff if is_executable(f)])
        df.at[index, 'Last_comp'] = str(datetime.now().replace(microsecond=0))

        move_compiled_files(diff, repo_folder)
        clean_up([before, after])
        db_handler.wrapup(df)
        print(f"Done: {repo_folder}\n")


if __name__ == "__main__":
    main()
