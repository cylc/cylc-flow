#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2015 NIWA
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
# Test validation of example suites
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------

TEST_NAME=$TEST_NAME_BASE

SDEFS=$(find $CYLC_DIR/examples -name suite.rc)
set_test_number $(echo "$SDEFS" | wc -l)

for SDEF in $SDEFS; do
    # capture validation stderr:
    SDEF_NAME=$(basename $(dirname $SDEF))
    RES=$( cylc val --no-write --debug $SDEF 2>&1 >/dev/null )
    TEST_NAME=$TEST_NAME_BASE-$TEST_NUMBER-"$SDEF_NAME"
    if [[ -n $RES ]]; then
        fail $TEST_NAME
        echo "$SDEF failed validation" >$TEST_NAME.stderr
        echo "$RES" >>$TEST_NAME.stderr
        mkdir -p $TEST_LOG_DIR
        cp $TEST_NAME.stderr $TEST_LOG_DIR/
    else
        ok $TEST_NAME
    fi
done
