#!/bin/bash

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2015 NIWA
#C: 
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.

set -e

CYLC=$(dirname $0)/../../bin/cylc

function usage {
    echo "USAGE make.sh"
}

if [[ $# != 0 ]]; then
    usage
    exit 1
fi

DEST=pdf
rm -rf $DEST; mkdir -p $DEST

$CYLC -v > cylc-version.txt

cp -r *.tex cylc-version.txt titlepic.sty $DEST
cd $DEST
ls *.tex | xargs -n 1 perl -pi -e 's@graphics/png/orig@../graphics/png/orig@g'
ls *.tex | xargs -n 1 perl -pi -e 's@\.\./examples/@../../examples/@g'
ls *.tex | xargs -n 1 perl -pi -e 's@\.\./conf/@../../conf/@g'
perl -pi -e 's@categories/@../categories/@g' commands.tex
perl -pi -e 's@commands/@../commands/@g' commands.tex
perl -pi -e 's@cylc.txt@../cylc.txt@g' commands.tex
perl -pi -e 's@\.\./README@../../README@g' cug.tex
perl -pi -e 's@\.\./INSTALL@../../INSTALL@g' cug.tex

# run pdflatex three times to resolve all cross-references
pdflatex -halt-on-error cug-pdf.tex
pdflatex -halt-on-error cug-pdf.tex
pdflatex -halt-on-error cug-pdf.tex

