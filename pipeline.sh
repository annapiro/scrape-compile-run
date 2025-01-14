#!/bin/bash

# exit if a command fails
set -e

# flag to indicate whether the script is ready to exit
exit_flag=false

wrapup() {
    printf "\n*** Process will terminate at the end of the current iteration. ***\n\n"
    exit_flag=true
}

trap wrapup SIGTERM

while true; do
    printf "\n*** Download ***\n\n"
    python3 scripts/toggler.py download --q "Last_comp.isna()" --size 15
    printf "\n*** Compile ***\n\n"
    python3 scripts/compiler.py
    printf "\n*** Archive ***\n\n"
    python3 scripts/archiver.py
    printf "\n *** Clean up ***\n\n"
    python3 scripts/toggler.py remove

    if [ "$(ls -A out/source)" ]; then
        printf "\n*** Exiting because out/source is not empty ***\n"
        break
    fi

    rm -rf out/build out/archive

    if [ "$exit_flag" = true ]; then
        break
    fi 
done
