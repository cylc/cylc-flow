#!/bin/bash

# exit immediately on error
set -e

USG=$CYLC_DIR/examples/userguide
TMPDIR={$TMPDIR:-/tmp/$USER}

GRP=CylcTest
REG1=${GRP}:foooo123
REG2=${GRP}:baaar123
REG3=${GRP}:baaaz123
REG4=${GRP}:waaaz123

echo
# register a suite as $REG1
cylc db reg $REG1 $USG
echo
# change the registration to $REG2
# this deletes the $REG1 registration
cylc db rereg $REG1 $REG2
echo
# copy the registeration only to $REG3
cylc db copy $REG2 $REG3
echo
# copy the registeration and suite to $REG4
cylc db copy $REG2 $REG4 $TMPDIR/$REG4
echo
# print registrations 
cylc db pr --gfilt=$GRP
echo
# delete one registration
cylc db unreg $REG2
echo
# delete the rest of 'em
cylc db unreg ${GRP}:
echo
# delete copied suite (fails if copied failed)
rm -r $TMPDIR/$REG4
# all gone?
cylc db pr --gfilt=$GRP
echo
