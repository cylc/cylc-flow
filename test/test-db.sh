#!/bin/bash

# This is a thorough test of cylc suite registration database
# functionality (local and central).

# exit immediately on error
set -e

USG=$CYLC_DIR/examples/userguide
TMPDIR=${TMPDIR:-/tmp/$USER}

GRP=Z1TCylcTestXaQ
REG1=${GRP}:foooo123
REG2=${GRP}:baaar123
REG3=${GRP}:baaaz123
REG4=${GRP}:waaaz123
REG5=${GRP}:impppt123

# clean up old suite def dirs from any aborted previous run
rm -rf $TMPDIR/$REG4
rm -rf $TMPDIR/$REG5

echo
echo "> TEST1: register a cylc example suite as $REG1"
cylc db reg $REG1 $USG

echo
echo "> TEST2: reregister $REG1 as $REG2"
cylc db rereg $REG1 $REG2

echo
echo "> TEST3: copy $REG2 to $REG3 (registration only)"
cylc db copy $REG2 $REG3

echo
echo "> TEST4: copy the registeration and suite to $REG4"
cylc db copy $REG2 $REG4 $TMPDIR/$REG4

echo
echo "> TEST5: print LDB reg group $GRP"
cylc db pr --gfilt=$GRP

echo
echo "> TEST6: export $REG2 to CDB"
cylc db exp $REG2

echo
echo "> TEST7: export the whole group to CDB"
cylc db exp ${GRP}:

echo
echo "> TEST8: print CDB reg group $GRP:"
cylc db pr -o $USER -g ${GRP}

echo
echo "> TEST9: import central $REG4 as $REG5"
cylc db imp ${USER}:$REG4 $REG5 $TMPDIR/$REG5

echo
echo "> TEST10: delete $REG2 from CDB"
cylc db unreg ${USER}:$REG2

echo
echo "> TEST11: the rest of group $GRP from CDB"
# delete the rest of the CDB group
cylc db unreg ${USER}:${GRP}:

echo
echo "> TEST12: print CDB group $GRP (should be empty)"
cylc db pr -o $USER -g $GRP

echo
echo "> TEST13: delete $REG2 from LDB"
cylc db unreg $REG2

echo
echo "> TEST14: delete the regst of group $GRP from LDB"
cylc db unreg ${GRP}:

echo
echo "> TEST15: delete the copied suite definitions"
rm -r $TMPDIR/$REG4
rm -r $TMPDIR/$REG5
echo "DONE" # fake the DONE emitted by cylc commands 

echo
echo "> TEST16: print LDB group $GRP (should be empty)"
cylc db pr --gfilt=$GRP
