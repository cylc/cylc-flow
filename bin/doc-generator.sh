#!/bin/bash

set -e

# generate pdf documentation from cylon LaTeX source

usage() {
	echo "USAGE: [-f] $0"
    echo ' -f, force re-conversion of eps figures to PDF'
	echo "Run script in the cylon top level directory"
}

[[ $# > 1 ]] && {
    usage
	exit 1
}

FORCE=false
if [[ $# == 1 ]]; then 
    if [[ $1 = '-f' ]]; then
        FORCE=true
    else
        usage
        exit 1
    fi
fi

[[ ! -f bin/cylon ]] && {
	echo "RUN THIS SCRIPT IN THE CYLON TOP LEVEL DIRECTORY"
    usage
	exit 1
}

cd doc

for F in *.eps; do
    [[ ! -f ${F%eps}pdf ]] || $FORCE && {
        echo converting $F to PDF
        epstopdf $F
    }
done

pdflatex cylon.tex
