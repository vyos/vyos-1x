#!/bin/bash

# Check if a directory argument is provided
if [ -z "$1" ]; then
  exit 1
fi

# Assign the first argument to DIR variable
DIR=$1

# Check if the provided argument is a directory
if [ ! -d "$DIR" ]; then
  exit 1
fi

# List only the files in the directory
find "$DIR" -maxdepth 1 -type f -exec basename {} \;
