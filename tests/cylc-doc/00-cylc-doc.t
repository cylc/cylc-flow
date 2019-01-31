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
# Test the cylc-doc command on printing cylc URLs.
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 4
#-------------------------------------------------------------------------------
LOCAL="local = ${PWD}/doc/built-sphinx/index.html"
ONLINE='http://cylc.github.io/cylc/doc/built-sphinx/index.html'
create_test_globalrc "" "
[documentation]
    local = ${LOCAL}
    online = ${ONLINE}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-online"
run_ok "${TEST_NAME}" cylc doc -s
cmp_ok "${TEST_NAME}.stdout" <<< "${ONLINE}"
TEST_NAME="${TEST_NAME_BASE}-local"
run_ok "${TEST_NAME}" cylc doc -s --local
cmp_ok "${TEST_NAME}.stdout" <<< "${LOCAL}"
