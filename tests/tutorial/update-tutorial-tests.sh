#!/bin/bash

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

set -e

# Run this from inside tests/tutorial/.
export CYLC_TEST_TIME_INIT=$(date -I)
export CYLC_TEST_RUN_GENERIC=true
export CYLC_TEST_RUN_PLATFORM=true

#for GROUP in oneoff cycling; do
for GROUP in cycling; do
    rm -r $GROUP
    mkdir -p $GROUP
    cd $GROUP
    GDIR=$PWD
    [[ ! -L test_header_tutorial ]] && ln -s ../test_header_tutorial
    [[ ! -L test_header ]] && ln -s ../../lib/bash/test_header

    # 1) MAKE SYMLINKS TO ALL TUTORIAL SUITES
    # remove old symlinks
    rm -f tut.*
    # generate new symlinks
    for SRCE in ../../../etc/examples/tutorial/$GROUP/*; do
        ln -s $SRCE tut.$(basename $SRCE )
    done

    # 2) GENERATE REFERENCE LOGS FOR **NEW** TUTORIAL SUITES
    REFLOGS=$GDIR/reflogs
    mkdir -p $REFLOGS

    . test_header_tutorial
    . test_header # (this cds to the test dir)

    for DIR in $GDIR/tut.*; do
        NAME=$( basename $DIR )
        if [[ ! -f $REFLOGS/$NAME ]]; then
            # ref log does not exist, generate a new one
            install_suite $NAME $NAME
            alter_suite
            cylc run --reference-log --no-detach $SUITE_NAME
            cp $TEST_DIR/$SUITE_NAME/reference.log $REFLOGS/$NAME
            purge_suite $SUITE_NAME
        fi
    done

    # 3) MAKE TEST SCRIPTS FOR ALL TUTORIAL SUITES
    cd $GDIR
    rm -f *.t
    COUNT=0
    for DIR in $GDIR/tut.*; do
        NAME=$( basename $DIR )
        I=$( printf "%02d" $COUNT )
        cat > ${I}-${NAME}.t <<EOF
#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#-------------------------------------------------------------------------------
# Test CUG tutorial suites

# *** WARNING THIS TEST GENERATED AUTOMATICALLY BY update-tutorial-tests.sh ***

. \$(dirname \$0)/test_header_tutorial
. \$(dirname \$0)/test_header
#-------------------------------------------------------------------------------
set_test_number 2
#-------------------------------------------------------------------------------
install_suite \$TEST_NAME_BASE $NAME
alter_suite
#-------------------------------------------------------------------------------
TEST_NAME=\$TEST_NAME_BASE-val
run_ok \$TEST_NAME cylc validate \$SUITE_NAME
#-------------------------------------------------------------------------------
TEST_NAME=\$TEST_NAME_BASE-run
suite_run_ok \$TEST_NAME cylc run --reference-test --no-detach --debug \$SUITE_NAME
#-------------------------------------------------------------------------------
purge_suite \$SUITE_NAME
EOF
        (( COUNT+=1 ))
    done

    cd ..
done
