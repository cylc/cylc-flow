#!/bin/bash

PDFLATEX=$( which pdflatex 2> /dev/null )
HTLATEX=$(  which htlatex  2> /dev/null )
CONVERT=$(  which convert  2> /dev/null )

WARNED=false

if [[ -z $PDFLATEX ]]; then
    echo "*** WARNING: to generate PDF Cylc documentation install LaTeX pdflatex ***" >&2
    WARNED=true
else
    DEPS="pdf"
fi

if [[ -z $HTLATEX ]]; then
    echo
    echo "*** WARNING: to generate HTML Cylc documentation install LaTeX tex4ht ***" >&2
    WARNED=true
fi

if [[ -z $CONVERT ]]; then
    echo "*** WARNING: to generate HTML Cylc documentation install ImageMagick convert ***" >&2
    WARNED=true
fi

if [[ -n $CONVERT && -n $HTLATEX ]]; then 
    DEPS="$DEPS html"
fi

if $WARNED; then
    # pause to ensure warnings are noticed.
    sleep 2
fi

echo $DEPS
