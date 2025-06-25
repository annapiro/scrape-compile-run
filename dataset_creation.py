"""
Process a directory of downloaded repos to create a JSONL dataset of C code.
Only files that contain the main() function are considered.
"""

import json
import os
import re

import chardet
from dotenv import load_dotenv
from pycparser import parse_file

from src.db_handler import initialize, wrapup, match_folder_to_row, EmptyDatasetError

load_dotenv()
DATASET_SRC = os.path.join(*os.getenv('DATASET_SRC').split('/'))
DATASET_TARGET = os.path.join(*os.getenv('DATASET_TARGET').split('/'))


def has_main_function(code: str) -> bool:
    """
    Check whether given C code contains a main() function
    :param code: Code to check in string format, newlines included
    :return: True or False
    """
    # clean the code from comments to reduce false positives
    pattern_comments = r'/\*[\s\S]*?\*/|//.*'
    code_cleaned = re.sub(pattern_comments, '', code)
    # check if the cleaned code contains a main function definition
    pattern_main = r'\bmain\(.*?\)[\s\n]*{'
    return bool(re.search(pattern_main, code_cleaned))


def serialize_to_jsonl(list_of_entries: list[dict], file_name: str, save_to=DATASET_TARGET):
    """
    Process a list of dictionaries into a JSONL file
    :param list_of_entries: List of dictionaries containing the data where each dictionary is a new entry in the dataset
    :param file_name: .jsonl file name for the dataset
    :param save_to: Directory where the JSONL should be saved; uses the .env setting by default
    """
    os.makedirs(save_to, exist_ok=True)
    with open(os.path.join(save_to, file_name), 'a') as f:
        for entry in list_of_entries:
            json.dump(entry, f)
            f.write("\n")


def main():
    df, _ = initialize()
    if df.empty:
        raise EmptyDatasetError()

    # check if the dataframe is already tracking each repo's dataset status
    if 'In_dataset' not in df:
        df['In_dataset'] = False

    dataset_entries = []

    # get a list of available repo folders
    folders = [x for x in os.listdir(DATASET_SRC) if os.path.isdir(os.path.join(DATASET_SRC, x))]

    for repo_folder in folders:
        # match every folder to df to get more data about the repo
        df_row = match_folder_to_row(repo_folder, df)
        # skip unmatched repos and those that are already tagged as in dataset
        if df_row is None or df_row.In_dataset:
            continue
        for root, _, files in os.walk(os.path.join(DATASET_SRC, repo_folder)):
            for f in files:
                # for every .c file, check if it has a main() function
                if not f.endswith('.c'):
                    continue
                filepath = os.path.join(root, f)

                # read the file in binary mode to detect encoding
                with open(filepath, 'rb') as bin_file:
                    raw_data = bin_file.read()
                result = chardet.detect(raw_data)
                encoding = result['encoding']
                # print(f"Detected encoding: {encoding} (confidence: {result['confidence']})")
                
                try:
                    with open(filepath, 'r', encoding=encoding) as code_file:
                        code = code_file.read()
                except UnicodeDecodeError as e:
                    print(f"Exception reading {os.path.join(root, f)} with encoding {encoding}: {e}")
                    continue
              
                if not has_main_function(code):
                    continue
                # TODO check the file for well-formedness (maybe with gcc?)
                # if the file passes the checks, add it to the dictionary
                new_entry = {
                    'repo_name': df_row.name,
                    'path': os.path.relpath(filepath, os.path.join(DATASET_SRC, repo_folder)),
                    'stars': int(df_row.Stars),
                    'repo_size': int(df_row.Size),
                    'code': code,
                }
                dataset_entries.append(new_entry)
        df.at[df_row.name, 'In_dataset'] = True

    # after everything is done, write to a .jsonl file
    serialize_to_jsonl(dataset_entries, file_name='dataset.jsonl')
    wrapup(data=df)


if __name__ == "__main__":
    try:
        main()
    except EmptyDatasetError as e:
        print(e)
