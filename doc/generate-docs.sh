#!/bin/bash

set -e

# generate pdf documentation from cylc LaTeX source

usage() {
	echo "USAGE: [-f] $0"
    echo ' -f, force re-conversion of eps figures to PDF'
	echo "Run script in the cylc top level directory"
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

# extract command help output
mkdir -p doc/command-usage
cylc            --help > doc/command-usage/cylc.txt
cylc server     --help > doc/command-usage/cylc-server.txt
cylc control    --help > doc/command-usage/cylc-control.txt
cylc configure  --help > doc/command-usage/cylc-configure.txt
cylc monitor    --help > doc/command-usage/monitor.txt

cd doc

for F in *.eps; do
    [[ ! -f ${F%eps}pdf ]] || $FORCE && {
        echo converting $F to PDF
        epstopdf $F
    }
done

#pdflatex cylc.tex
latex cylc.tex
dvipdf cylc.dvi
