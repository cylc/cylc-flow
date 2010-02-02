#!/bin/bash

#set -e

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

[[ ! -f bin/cylc ]] && {
	echo "RUN THIS SCRIPT IN THE CYLC TOP LEVEL DIRECTORY"
    usage
	exit 1
}

# extract command help output
cylc                 --help > doc/command-usage/cylc.txt
cylc server          --help > doc/command-usage/cylc-server.txt
cylc control         --help > doc/command-usage/cylc-control.txt
cylc monitor-all     --help > doc/command-usage/monitor-all.txt
cylc monitor-running --help > doc/command-usage/monitor-running.txt
cylc monitor-pyro-ns --help > doc/command-usage/monitor-pyro-ns.txt
cylc monitor-dummies --help > doc/command-usage/monitor-dummies.txt

cd doc

for F in *.eps; do
    [[ ! -f ${F%eps}pdf ]] || $FORCE && {
        echo converting $F to PDF
        epstopdf $F
    }
done

pdflatex cylc.tex
