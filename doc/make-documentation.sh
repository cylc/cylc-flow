#!/bin/bash

set -e

# generate pdf documentation from cylc LaTeX source

usage() {
	echo "USAGE: [-f] $0"
    echo ' -f, force re-conversion of eps figures to PDF'
    echo "Run this script in the top level of your cylc repository"
}

[[ $# > 1 ]] && {
    usage
	exit 1
}

if [[ ! -f bin/cylc ]]; then
    echo "Run this script in the top level of your cylc repository"
    exit 1
fi

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
echo hello
mkdir -p doc/command-usage
cylc help > doc/command-usage/cylc-help.txt
for command in configure register start stop pause resume nudge \
    set-level reset kill purge insert ask message run-task monitor monitor-r \
    monitor-d monitor-p; do
    echo "cylc $command --help"
    cylc $command --help > doc/command-usage/cylc-$command.txt
done

#Comment-stripped taskdef files:
#perl -e 'while (<>) { if ( ! m/^\s*#/ && ! m/^\s*$/ ) { print }}' < \
#    sys/examples/userguide-1/system_config.py > doc/system_config.py.stripped
#perl -e 'while (<>) { if ( ! m/^\s*#/ && ! m/^\s*$/ ) { print }}' < \
#    sys/templates/full-template.def > doc/full-template.def.stripped


cd doc

cd inkscape-svg
for F in *.eps; do
    [[ ! -f ${F%eps}pdf ]] || $FORCE && {
        echo converting $F to PDF
        epstopdf $F
    }
done
cd ..

#pdflatex userguide.tex
latex userguide.tex
dvipdf userguide.dvi
