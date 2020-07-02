#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
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
# ensure that CYLC_CONF_PATH works correctly
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 7
#-------------------------------------------------------------------------------
mkdir foo
mkdir bar
echo 'process pool size = 1' > 'foo/flow.rc'
echo 'process pool size = 1234' > 'foo/mess.rc'

# if we point CYLC_CONF_PATH at a dir Cylc should load the
# flow.rc within it
TEST_NAME="${TEST_NAME_BASE}-dir"
export CYLC_CONF_PATH=foo
run_ok "${TEST_NAME}" cylc get-site-config --sparse
cmp_ok "${TEST_NAME}.stdout" << __HERE__
process pool size = 1
__HERE__

# if we point CYLC_CONF_PATH at a particular file Cylc should load
# that particular file
TEST_NAME="${TEST_NAME_BASE}-file"
export CYLC_CONF_PATH=foo/mess.rc
run_ok "${TEST_NAME}" cylc get-site-config --sparse
cmp_ok "${TEST_NAME}.stdout" << __HERE__
process pool size = 1234
__HERE__

# if we point CYLC_CONF_PATH at a non-existent dir Cylc should
# raise an error (else tests could become placebos)
TEST_NAME="${TEST_NAME_BASE}-missing-dir"
export CYLC_CONF_PATH=foot
run_fail "${TEST_NAME}" cylc get-site-config --sparse

# if we point CYLC_CONF_PATH at a non-existent file Cylc should
# raise an error (else tests could become placebos)
TEST_NAME="${TEST_NAME_BASE}-missing-file"
export CYLC_CONF_PATH=foo/foot.rc
run_fail "${TEST_NAME}" cylc get-site-config --sparse

# if we point CYLC_CONF_PATH at a directory which doesn't contain
# a config file Cylc should raise an error (else tests could become placebos)
TEST_NAME="${TEST_NAME_BASE}-no-config-file"
export CYLC_CONF_PATH=bar
run_fail "${TEST_NAME}" cylc get-site-config --sparse

rm -r foo bar

exit
