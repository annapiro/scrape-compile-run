import csv
from datetime import datetime
import os
import shutil
import subprocess

from dotenv import load_dotenv
from tqdm import tqdm

import db_handler

load_dotenv()

# get directory paths and replace path separators with ones used by the system
SOURCE_DIR = os.path.join(*os.getenv('SOURCE_DIR').split('/'))
BUILD_DIR = os.path.join(*os.getenv('COMPILE_DIR').split('/'))
LOG_DIR = os.path.join('out', 'logs')


def run_cmake_make(path: str, cmakelists: str = None) -> (str, list, str, str):
    """
    :param path: Directory where Makefile is located or will be generated
    :param cmakelists: Path to CMakeLists.txt if it needs to be run first
    :return: executed command(s), list of target files, stdout, stderr
    """
    process_log = []
    target_log = []

    # run CMakeLists.txt first if it's available
    if cmakelists:
        # make CMakeLists.txt path relative to the repo root
        # TODO this is bad, use relpath
        cmakelists_rel = cmakelists.replace(path, '').strip(os.path.sep)
        print(f'Run cmake: {path}')
        command = ['cmake', cmakelists_rel]
        returncode, out, err = run_subprocess(command, path)

        # logging
        process_log.append(command[0])
        target_log.append(cmakelists)
        if returncode != 0:
            return '-'.join(process_log), target_log, out, err

    # run Makefile
    print(f'Run make: {path}')
    command = ['make', 'V=1']
    _, out, err = run_subprocess(command, path)

    # logging
    process_log.append(command[0])
    target_log.append(os.path.join(path, "Makefile"))
    return '-'.join(process_log), target_log, out, err


def run_gcc(repo_path: str, cfiles: list) -> (str, list, str, str):
    """
    :return: executed command, list of target files, stdout, stderr
    """
    output_file = 'compiled_output'
    cfiles_relative = [os.path.relpath(f, repo_path) for f in cfiles]
    print(f'Run gcc: {repo_path}')
    command = ['gcc'] + cfiles_relative + ['-o', output_file]
    _, out, err = run_subprocess(command, repo_path)
    return command[0], cfiles, out, err


def run_subprocess(command: list, cwd: str) -> (int, str, str):
    """
    :return: subprocess return code, stdout and stderr
    """
    # return None, 'dummy', 'dummy'  # debug
    try:
        result = subprocess.run(command,
                                cwd=cwd,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True,
                                timeout=60)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired as e:
        print('Timeout')
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

    depth = len(os.path.relpath(file_path, root_path).split(os.sep)) - 1

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
            for name in dirs + files:
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


def move_compiled_files(compiled_paths: list[str], repo_path: str):
    for item_path in compiled_paths:
        if os.path.isfile(item_path):
            # remove source directory prefix or cwd prefix
            # TODO too crude
            stripped_path = item_path.replace(SOURCE_DIR + os.path.sep, '', 1).replace(os.getcwd() + os.path.sep, '', 1)
            new_path = os.path.join(BUILD_DIR, repo_path, stripped_path)
            os.makedirs(new_path, exist_ok=True)
            shutil.move(item_path, new_path)
            # only report new executables
            if os.access(new_path, os.X_OK) or new_path.lower().endswith('.exe'):
                print(f"New: {new_path}")


def find_executables(file_paths: list[str]) -> list[str]:
    execs: list[str] = []
    for file_path in file_paths:
        if os.path.isfile(file_path):
            if is_executable(file_path):
                # TODO revise
                stripped_path = file_path.replace(SOURCE_DIR + os.path.sep, '', 1).replace(os.getcwd() + os.path.sep, '', 1)
                execs.append(stripped_path)
    return execs


def is_executable(filepath: str) -> bool:
    _, output, _ = run_subprocess(command=['file', filepath], cwd='.')
    output = output.strip('\n')
    # trim the file name from the output
    file_description = output.split(': ', 1)[1].lower()
    if 'executable' in file_description:
        if 'text executable' not in file_description:
            return True
    return False


def clean_up(files_to_rm: list[str]):
    """
    Remove files with listed filepaths
    """
    for f in files_to_rm:
        os.remove(f)


def update_log(repo_path: str, diff: list, process: str, targets: list, output: str, error: str):
    log_file = os.path.join(LOG_DIR, 'compiler_output.csv')
    file_exists = os.path.isfile(log_file)

    # clean diff paths
    new_files_rel = []
    for path in diff:
        new_files_rel.append(os.path.relpath(path, start=repo_path))

    # clean target paths
    # list of targets can be very long, so only log the last 10 items
    targets_rel = []
    for path in targets[-10:]:
        targets_rel.append(os.path.relpath(path, start=repo_path))
    targets_str = f"(...) {targets_rel}" if len(targets) > 10 else str(targets_rel)

    # clean repo path
    repo_path = repo_path.strip(os.sep)
    if SOURCE_DIR in repo_path:
        repo_path = os.path.relpath(repo_path, start=SOURCE_DIR)
    repo_path = repo_path.split(os.sep)[0]

    timestamp = datetime.now()

    with open(log_file, 'a', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        if not file_exists:
            writer.writerow(['Repo', 'Process', 'Target', 'Output', 'Error', 'New files', 'Timestamp'])
        writer.writerow([os.path.basename(repo_path), process, targets_str, output, error, new_files_rel, timestamp])


def main():
    # repos = os.scandir(SOURCE_DIR)
    os.makedirs(LOG_DIR, exist_ok=True)
    df, _ = db_handler.initialize()

    # only iterate through the repos that are saved to disk
    filtered_df = df[df['On_disk']].copy()

    for index, row in tqdm(filtered_df.iterrows()):
        repo_path = os.path.join(SOURCE_DIR, row['Folder'])

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

        # process, targets, output, error
        result: list[str | list | None] = [None, [], None, None]

        # assuming there's Makefile or CMakeLists in root
        cmakelists_path = os.path.join(repo_path, 'CMakeLists.txt')
        makefile_path = os.path.join(repo_path, 'Makefile')

        if os.path.isfile(cmakelists_path):
            result = run_cmake_make(repo_path, cmakelists_path)
        elif os.path.isfile(makefile_path):
            result = run_cmake_make(repo_path)
        else:
            # walk the repo and find the next best option
            makefiles, cmakelists, cfiles = get_relevant_files(repo_path)
            if cmakelists:
                cmakelists_path = find_best_file(cmakelists)
                result = run_cmake_make(repo_path, cmakelists_path)
            elif makefiles:
                makefile_path = find_best_file(makefiles)
                makefile_dir = os.path.dirname(makefile_path)
                result = run_cmake_make(makefile_dir)
            elif cfiles:
                result = run_gcc(repo_path, cfiles)

        save_dir_structure(repo_path, after)
        save_dir_structure(os.getcwd(), after, recurse=False)
        diff = compare_dir_structure(before, after)
        new_files = [os.path.relpath(fpath, start=SOURCE_DIR) for fpath in diff]
        execs = find_executables(diff)

        df.at[index, 'Process'] = result[0]
        df.at[index, 'Out'] = result[2]
        df.at[index, 'Err'] = result[3]
        df.at[index, 'New_files'] = '\n'.join(new_files)
        df.at[index, 'Execs'] = '\n'.join(execs)
        df.at[index, 'Last_comp'] = datetime.now().replace(microsecond=0)

        update_log(repo_path=repo_path,
                   diff=diff,
                   process=result[0],
                   targets=result[1],
                   output=result[2],
                   error=result[3])

        move_compiled_files(diff, os.path.basename(repo_path))
        clean_up([before, after])
        db_handler.wrapup(df)
        print(f"Done: {repo_path}\n")


if __name__ == "__main__":
    main()
