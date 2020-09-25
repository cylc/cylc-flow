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
# Test validation fails on bad task event handler templates.
. "$(dirname "$0")/test_header"

set_test_number 4

TEST_NAME="${TEST_NAME_BASE}-bad-key"
cat >'flow.cylc' <<'__FLOW_CONFIG__'
[scheduling]
    [[graph]]
        R1=t1
[runtime]
    [[t1]]
        script=true
        [[[events]]]
            failed handler = echo %(id)s, echo %(rubbish)s
__FLOW_CONFIG__
run_fail "${TEST_NAME}" cylc validate 'flow.cylc'
cmp_ok "${TEST_NAME}.stderr" <<'__ERR__'
SuiteConfigError: bad task event handler template t1: echo %(rubbish)s: KeyError('rubbish')
__ERR__

TEST_NAME="${TEST_NAME_BASE}-bad-value"
cat >'flow.cylc' <<'__FLOW_CONFIG__'
[scheduling]
    [[graph]]
        R1=t1
[runtime]
    [[t1]]
        script=true
        [[[events]]]
            failed handler = echo %(ids
__FLOW_CONFIG__
run_fail "${TEST_NAME}" cylc validate 'flow.cylc'
cmp_ok "${TEST_NAME}.stderr" <<'__ERR__'
SuiteConfigError: bad task event handler template t1: echo %(ids: ValueError('incomplete format key')
__ERR__

exit
