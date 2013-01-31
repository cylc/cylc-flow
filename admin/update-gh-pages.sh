#!/bin/bash

set -e
set -x

function usage {
cat <<eof
USAGE update-gh-pages.sh [-p] COMMIT-MESSAGE

Check out gh-pages, update its files from doc/ in master branch, and
then optionally [-p] push to the cylc repository on github.

Before running this you should 'make html-single' in the master doc
directory and record any changes to the single-page html user guide or
its css file (and any changes to doc/online/index.html).

eof
}

if [[ $# < 1 ]]; then
    usage
    exit 1
fi

PUSH=false
if [[ $1 == -p ]]; then
    PUSH=true
    shift
fi

if [[ $# == 0 ]]; then
    usage
    exit 1
fi

COMMITMSG=$@

LATESTTAG=$( git describe --abbrev=0 --tags )

[[ -z $COMMITMSG ]] && exit 1

# make html user guides
cd doc
make html

# cp online content to a temp dir
TMPD=$( mktemp -d )
cp -r gh-pages/ graphics/ html/ $TMPD/

# return to top level
cd ..

# checkout gh-pages branch
git checkout gh-pages

# replace the online content
cp -r $TMPD/gh-pages/* .
cp $TMPD/html/single/*.{css,html} html/single/
cp $TMPD/html/multi/*.{css,html} html/multi/
cp $TMPD/graphics/png/scaled/* graphics/png/scaled/
# substitute latest version number in the homepage
perl -pi -e "s@(Current Version:).*(<a)@\1 <a href=\"#download\">$LATESTTAG</a> ($( date +%F )) \2@" index.html

# any changes to update?
git update-index -q --refresh
if [[ -n "$(git diff-index --name-only HEAD --)" ]]; then 
    echo "committing changes"; 
    git commit -a -m "$COMMITMSG"
else 
    # (attempted commit is an error if there's nothing to commit)
    echo "no changes to commit";
fi

# push to github if requested
$PUSH && git push cylc gh-pages

# return to master
git checkout master

echo "DONE: gh-pages updated."

