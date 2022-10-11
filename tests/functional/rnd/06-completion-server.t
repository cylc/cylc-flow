#!/usr/bin/env bash
# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
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

. "$(dirname "$0")/test_header"
set_test_number 6

# NOTE: The completion server is heavily unit-tested
# Run a couple of quick functional tests to make sure the CLI interface / reading
# from stdin is working correctly.

# $ cylc t<tab><tab>
# tui
# trigger
TEST_NAME="${TEST_NAME_BASE}-t"
run_ok "${TEST_NAME}" cylc completion-server --once <<< 'cylc|t'
grep_ok trigger "${TEST_NAME}.stdout"
grep_ok tui "${TEST_NAME}.stdout"

# $ cylc trigg<tab><tab>
# trigger
TEST_NAME="${TEST_NAME_BASE}-trigg"
run_ok "${TEST_NAME}" cylc completion-server --once <<< 'cylc|trigg'
cmp_ok "${TEST_NAME}.stdout" << __HERE__
trigger
__HERE__

# Make sure the server exits timeout when trying to read from stdin
# (Note the completion server exits 0 on timeout)

TEST_NAME="${TEST_NAME_BASE}-timeout"
run_ok "${TEST_NAME}" timeout 5 cylc completion-server --timeout=1

exit
