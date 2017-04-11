#!/bin/bash
set -e

rm -r doc html
mkdir doc
cp ~/install/cylc-user-guide.pdf doc/
cp ~/install/suite-design-guide.pdf doc/
for f in ~/install/html/{single,multi}/*.{html,css}; do
    F=${f#*install/}
    echo $F
    mkdir -p $(dirname $F)
    cp $f $F
done
git checkout -- doc/cylc-autosub-response.pdf

echo "Now add and commit any new files under html"
git status
