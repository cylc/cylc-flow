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

# Test that undeclared zero-offset clock xtriggers are allowed.
. "$(dirname "$0")/test_header"

set_test_number 1

cat >'flow.cylc' <<'__FLOW_CONFIG__'
[scheduler]
    allow implicit tasks = True
[scheduling]
    initial cycle point = now
    [[graph]]
        T00 = "@wall_clock => foo"
__FLOW_CONFIG__

run_ok "${TEST_NAME_BASE}-val" cylc validate 'flow.cylc'
