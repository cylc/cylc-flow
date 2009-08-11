#!/bin/bash

set -e

# generate pdf documentation from cycon LaTeX source

[[ $# != 0 ]] && {
	echo "USAGE: $0"
	echo "run in cycon top level directory"
	exit 1
}


[[ ! -f bin/cycon ]] && {
	echo "RUN THIS IN CYCON REPO TOP LEVEL"
	exit 1
}

cd doc
pdflatex cycon.tex
