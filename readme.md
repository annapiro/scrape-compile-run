# C dataset collection
## Setup
Install the required packages:

`pip install -r requirements.txt`

Ensure that commands `make`, `cmake`, and `gcc` are available on your system.

Rename `.env.example` to `.env` and insert your GitHub API key (`API_KEY`). 

(Optional) Adjust the maximum allowed size for downloading repos (`SIZE_LIMIT`) and the directories for storing source code (`SOURCE_DIR`) and compiled output (`COMPILE_DIR`).

## Scrape

`py scraper.py`



## Compile

`py compiler.py`


## Run
future work