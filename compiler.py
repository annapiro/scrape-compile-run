import subprocess
import os
import shutil
import csv
from dotenv import load_dotenv
from datetime import datetime


load_dotenv()

# get directory paths and replace path separators with ones used by the system
SOURCE_DIR = os.path.join(*os.getenv('SOURCE_DIR').split('/'))
OUT_DIR = os.path.join(*os.getenv('COMPILE_DIR').split('/'))
LOG_DIR = os.path.join(*os.getenv('LOG_DIR').split('/'))


def do_compile(path: str, cmakelists: str = None) -> (list, str, str):
    """
    :param path: Directory where Makefile is located or will be generated
    :param cmakelists: Path to CMakeLists.txt if it needs to be run first
    :return: list of command arguments, stdout and stderr of the subprocess
    """
    # run CMakeLists.txt first if it's available
    if cmakelists:
        # make CMakeLists.txt path relative to the repo root
        cmakelists = cmakelists.replace(path, '').strip(os.path.sep)
        print(f'Run cmake: {path}')
        command = ['cmake', cmakelists]
        returncode, out, err = do_subprocess_run(command, path)
        if returncode != 0:
            return command, out, err
    # run Makefile
    print(f'Run make: {path}')
    command = ['make', 'V=1']
    _, out, err = do_subprocess_run(command, path)
    return command, out, err


def compile_cfiles_directly(repo_path: str, cfiles: list) -> (list, str, str):
    output_file = 'compiled_output'
    print(f'Run gcc: {repo_path}')
    command = ['gcc'] + cfiles + ['-o', output_file]
    _, out, err = do_subprocess_run(command, repo_path)
    return command, out, err


def do_subprocess_run(command: list, path: str) -> (int, str, str):
    """
    :return: subprocess return code, stdout and stderr
    """
    # return None, 'dummy', 'dummy'  # debug
    try:
        result = subprocess.run(command,
                                cwd=path,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True,
                                timeout=60)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired as e:
        print('Timeout')
        return None, None, str(e)


def get_relevant_files(root_path: str) -> (list, list, list):
    makefiles = []
    cmakelists = []
    cfiles = []
    
    print(f'Walk subdirs: {root_path}')
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

    return (priority, -depth)


def find_best_file(file_list: list) -> str:
    file_list.sort(key=lambda x: (x[1], x[2]), reverse=True)
    return file_list[0][0]


def save_dir_structure(path: str, fname: str):
    """
    List paths of all files and dirs contained in a root directory
    Save the output in a file
    """
    with open(fname, 'w', encoding='utf-8') as f:
        for root, dirs, files in os.walk(path):
            for name in dirs:
                f.write(os.path.join(root, name) + '\n')
            for name in files:
                f.write(os.path.join(root, name) + '\n')


def compare_dir_structure(before_file: str, after_file: str) -> list[str]:
    """
    Given two files (before and after changes), list new paths that were added
    """
    with open(before_file, 'r', encoding='utf-8') as f:
        before = set(f.read().splitlines())
    with open(after_file, 'r', encoding='utf-8') as f:
        after = set(f.read().splitlines())
    return list(after - before)


def move_compiled_files(compiled_paths: list[str]):
    for item_path in compiled_paths:
        if os.path.isfile(item_path):
            new_path = item_path.replace(SOURCE_DIR, OUT_DIR, 1)
            os.makedirs(new_path, exist_ok=True)
            shutil.move(item_path, new_path)
            print(f'New: {new_path}')


def clean_up(files_to_rm: list[str]):
    """
    Remove files with listed filepaths
    """
    for f in files_to_rm:
        os.remove(f)


def update_log(repo_path: str, command: list, output: str, error: str):
    log_file = os.path.join(LOG_DIR, 'compiler_output.csv')
    file_exists = os.path.isfile(log_file)
    process = command[0] if command else 'None'
    args = command[1:] if command else ''
    if len(args) > 5:
        args = f'(...) {args[-5:]}'
    
    timestamp = datetime.now()

    with open(log_file, 'a', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        if not file_exists:
            writer.writerow(['Repo', 'Process', 'Args', 'Output', 'Error', 'Timestamp'])
        writer.writerow([os.path.basename(repo_path), process, args, output, error, timestamp])


def process_repo(repo_path: str):
    before = 'before.txt'
    after = 'after.txt'

    # record initial repository structure
    save_dir_structure(repo_path, before)

    # assuming there's Makefile or CMakeLists in root
    makefile_path = os.path.join(repo_path, 'Makefile')
    cmakelists_path = os.path.join(repo_path, 'CMakeLists.txt')

    result = [None, None, None]

    if os.path.isfile(makefile_path):
        result = do_compile(repo_path)
    elif os.path.isfile(cmakelists_path):
        result = do_compile(repo_path, cmakelists_path)
    else:
        # walk the repo and find the next best option
        makefiles, cmakelists, cfiles = get_relevant_files(repo_path)

        if makefiles:
            makefile_path = find_best_file(makefiles)
            makefile_dir = os.path.dirname(makefile_path)
            result = do_compile(makefile_dir)
        elif cmakelists:
            cmakelists_path = find_best_file(cmakelists)
            result = do_compile(repo_path, cmakelists_path)
        elif cfiles:
            result = compile_cfiles_directly(repo_path, cfiles)

    update_log(repo_path, *result)

    save_dir_structure(repo_path, after)

    diff = compare_dir_structure(before, after)
    move_compiled_files(diff)
    clean_up([before, after])
    print(f'Done: {repo_path}\n')


def main():
    repos = os.scandir(SOURCE_DIR)
    for entry in repos:
        if entry.is_dir():
            process_repo(entry.path)


if __name__ == "__main__":
    main()
