#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2017 NIWA
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
# Test for https://github.com/cylc/cylc/issues/2064
. "$(dirname "$0")/test_header"

set_test_number 4

init_suite "${TEST_NAME_BASE}" "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/suite.rc"

run_ok "${TEST_NAME_BASE}-bar" \
    cylc get-config "${SUITE_NAME}" -i '[runtime][bar][dummy mode]script'
cmp_ok "${TEST_NAME_BASE}-bar.stdout" <<'__OUT__'
echo Dummy task; sleep $(cylc rnd 1 16)
sleep 2; cylc message 'greet'
__OUT__
run_ok "${TEST_NAME_BASE}-foo" \
    cylc get-config "${SUITE_NAME}" -i '[runtime][foo][dummy mode]script'
cmp_ok "${TEST_NAME_BASE}-foo.stdout" <<'__OUT__'
echo Dummy task; sleep $(cylc rnd 1 16)
__OUT__
purge_suite "${SUITE_NAME}"
exit
