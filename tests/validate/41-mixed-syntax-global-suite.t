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
# Test validatation error message, LHS suicide.
. "$(dirname "$0")/test_header"
set_test_number 1

cat >'global.rc' <<'__GLOBAL_RC__'
[cylc]
    [[event hooks]]
        timeout = P1D
__GLOBAL_RC__

cat >'suite.rc' <<'__SUITE_RC__'
[scheduling]
    [[dependencies]]
        graph = t0
[runtime]
    [[t0]]
        script = true
        [[[events]]]
            execution timeout = 10
__SUITE_RC__

CYLC_CONF_PATH="${PWD}" run_ok "${TEST_NAME_BASE}" cylc validate 'suite.rc'
exit
