#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2016 NIWA
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

# GitHub PR #2002 - validation of "foo | foo[-P1D] => bar" was failing because
# the explicit ':succeed' trigger was being substituted before the offset
# instead of after, creating an invalid trigger expression.

. "$(dirname "$0")/test_header"

set_test_number 1

cat >'suite.rc' <<'__SUITE_RC__'
[scheduling]
    initial cycle point = 2010
[[dependencies]]
    [[[P1D]]]
        graph = foo | foo[-P1D] => bar
[runtime]
    [[root]]
        script = true
__SUITE_RC__

run_ok "${TEST_NAME_BASE}" cylc validate 'suite.rc'

exit
