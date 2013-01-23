#!/bin/bash

PDFLATEX=$( which pdflatex 2> /dev/null )
HTLATEX=$(  which htlatex  2> /dev/null )
CONVERT=$(  which convert  2> /dev/null )

WARNED=false

if [[ -z $PDFLATEX ]]; then
    echo "*** WARNING: to generate the PDF User Guide install LaTeX pdflatex ***" >&2
    WARNED=true
else
    DEPS="pdf"
fi

if [[ -z $HTLATEX ]]; then
    echo
    echo "*** WARNING: to generate the HTML User Guides install LaTeX tex4ht ***" >&2
    WARNED=true
fi

if [[ -z $CONVERT ]]; then
    echo "*** WARNING: to generate the HTML User Guides install ImageMagick convert ***" >&2
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

