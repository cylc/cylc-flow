#!/bin/bash

set -e

echo
echo "PADDING FRAME NUMBERS"
for f in $(ls live-?.dot); do 
    echo mv $f ${f%-*}-0${f#*-}
    mv $f ${f%-*}-0${f#*-}
done

echo
echo "GENERATING IMAGES"
for f in live*.dot; do
    echo dot -Tpng -Gsize=9,9 -Nfontsize=50 -Estyle=bold -o ${f%dot}png $f
    dot -Tpng -Gsize=9,9\! -o ${f%dot}png $f
done

echo
echo "MODIFYING IMAGES"
for f in live*.png; do
    echo convert -resize 800x800 -background white -gravity left -extent 800x800 $f small-$f
    convert -quality 100 -resize x800 -background white -gravity West -extent 1200x800 $f small-$f
done

echo
echo "GENERATING mp4 movie"
echo ffmpeg -sameq -r 2 -f image2 -i small-live-%02d.png vid.mp4
ffmpeg -sameq -r 2 -f image2 -i small-live-%02d.png vid.mp4
