#!/bin/bash

# remove all evidence of document processing
if [[ ! -f doc/cug.tex ]]; then
    echo "Run this script from \$CYLC_DIR in your cylc repository."
    # We don't change to $CYLC_DIR automatically in case the environment
    # is configured for another cylc installation.
    exit 1
fi
echo Cleaning $PWD/doc
cd doc
rm -f *.4tc *.aux *.4ct *.dvi *.idv *.lg *.lof *.tmp *.toc *.xref *.out *.log *.css
rm -f *.html
rm -f *.pdf
rm -rf single
