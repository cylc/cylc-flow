#!/bin/bash

# cyclon example system, task startup
# one off initial task to clean the example system working directory
# no prerequisites

mkdir -p $TMPDIR || exit 1

echo "CLEANING $TMPDIR"
rm -rf $TMPDIR/* || exit 1
