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
mkdir -p doc/command-usage
cylc             help > doc/command-usage/cylc.txt
cylc configure --help > doc/command-usage/cylc-configure.txt
cylc register  --help > doc/command-usage/cylc-register.txt
cylc schedule  --help > doc/command-usage/cylc-scheduler.txt
cylc message   --help > doc/command-usage/cylc-message.txt
cylc control   --help > doc/command-usage/cylc-control.txt
cylc question  --help > doc/command-usage/cylc-question.txt
cylc monitor   --help > doc/command-usage/monitor.txt
cylc monitor-r   --help > doc/command-usage/monitor-r.txt
cylc monitor-d   --help > doc/command-usage/monitor-d.txt
cylc monitor-p   --help > doc/command-usage/monitor-p.txt
cylc run-task  --help > doc/command-usage/cylc-run-task.txt

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
