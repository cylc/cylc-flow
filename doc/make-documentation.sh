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

# GENERATE COMMAND REFERENCE CHAPTER CONTENTS -----------------------
rm -rf doc/command-usage; mkdir -p doc/command-usage
rm -f doc/commands.tex

for COMMAND in $(cylc commands); do 
    # direct command help into a txt file
    cylc $COMMAND --help > doc/command-usage/$COMMAND.txt
    # append to a latex file for inclusion in the userguide
    cat >> doc/commands.tex <<eof

\subsection{$COMMAND}
\label{$COMMAND}
\lstinputlisting{command-usage/$COMMAND.txt}

\pagebreak
eof

done
#-----------------------------------------------------------------------

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
