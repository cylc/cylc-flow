#!/usr/bin/env bash
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
# Test validating xtrigger names in suite.
. "$(dirname "$0")/test_header"

set_test_number 5

TEST_NAME="${TEST_NAME_BASE}-val"

# test a valid xtrigger
cat >'flow.cylc' <<'__FLOW_CONFIG__'
#!Jinja2
[scheduler]
    allow implicit tasks = True
[scheduling]
    initial cycle point = {{ ICP - 1 }}
    cycling mode = integer
    [[graph]]
        R1 = foo
__FLOW_CONFIG__
run_fail "${TEST_NAME}-valid" cylc validate flow.cylc
run_fail "${TEST_NAME}-valid" cylc validate flow.cylc -s 'ICP="2000"'
run_ok "${TEST_NAME}-valid" cylc validate flow.cylc -s 'ICP=2000'

cat >'template' <<'__TEMPLATE__'
ICP=2000
__TEMPLATE__
run_fail "${TEST_NAME}-valid" cylc validate flow.cylc
run_ok "${TEST_NAME}-valid" cylc validate flow.cylc --set-file=template

exit
