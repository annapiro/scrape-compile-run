# C dataset collection
## Setup
Install the required packages:

`pip install -r requirements.txt`

Ensure that commands `make`, `cmake`, and `gcc` are available on your system.

Rename `.env.example` to `.env` and insert your GitHub API key (`API_KEY`). 

(Optional) Adjust the maximum allowed size for downloading repos (`SIZE_LIMIT`) and the directories for storing the source code (`SOURCE_DIR`) and the compiled output (`COMPILE_DIR`).

## Main usage
This is a quick summary of how to run the main pipeline of the project, from finding repos to compiling them and collecting the artifacts. See the next section for more fine-grained control and detailed info on each pipeline step.  

### Scraper

Information about the repositories is stored in a pandas dataframe. You need to populate the dataframe before doing anything else. This is done by running the Scraper script:

`py -m src.scraper`

Scraper goes through 1000 C repos updated in the last month (1000 is the max number of search results returned by GitHub) and records them in the dataframe if they're eligible. Processed months are tracked between sessions, so the next time you run Scraper, it will start where it left off. 

By default, Scraper runs continuously until the script is terminated manually. You can also use command line arguments to stop scraping after a specified number of months. For example, this will stop the script after recording 3 months' worth of data:

`py -m src.scraper 3`

TODO: filtering criteria

### Pipeline

Start the pipeline by running:

`./pipeline.sh`

The steps of the pipeline are:
1. Download 100 random repos that have never been compiled before.
2. Run Compiler, which also moves any generated build files to a separate directory (use `.env` to set `COMPILE_DIR`). 
3. Run Archiver, which packages each successfully compiled repo's source files and generated executables in a zip archive.
4. Remove processed repositories from disk. (Note: If the source directory is not empty after this step, the pipeline stops.)
5. Remove leftover build files (only zip archives remain).
6. Repeat from the start.
   
The pipeline is designed to run automatically and continuously without user input. **To stop the process gracefully**, run the kill command (assuming it sends SIGTERM by default), which will allow the script to complete its current cycle before exiting:

```bash
kill [-SIGTERM] <pid>
```

Note that if an unexpected error occurs, especially during downloading or compilation, you might need to manually run some of the steps of the pipeline to finish the process that was interrupted.

## More details
### Scraper

### Toggler

### Compiler

### Archiver
