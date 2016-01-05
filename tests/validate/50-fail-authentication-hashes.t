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
# Test fail validation of bad vis node attributes.
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 4
#-------------------------------------------------------------------------------
cat >global.rc <<'__CONF__'
[authentication]
    hashes = md6
__CONF__
export CYLC_CONF_PATH=$PWD
TEST_NAME="$TEST_NAME_BASE-md6-get-global-config"
run_fail $TEST_NAME cylc get-global-config
grep_ok "hashes = md6" "$TEST_NAME.stderr"
#-------------------------------------------------------------------------------
cat >global.rc <<'__CONF__'
[authentication]
    scan hash = sha1048576
__CONF__
TEST_NAME="$TEST_NAME_BASE-sha-lots-get-global-config"
run_fail $TEST_NAME cylc get-global-config
grep_ok "scan hash = sha1048576" "$TEST_NAME.stderr"
exit
