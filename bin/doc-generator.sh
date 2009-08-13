#!/bin/bash

set -e

# generate pdf documentation from cyclon LaTeX source

[[ $# != 0 ]] && {
	echo "USAGE: $0"
	echo "run in cyclon top level directory"
	exit 1
}


[[ ! -f bin/cyclon ]] && {
	echo "RUN THIS IN CYCLON REPO TOP LEVEL"
	exit 1
}

cd doc
pdflatex cyclon.tex
