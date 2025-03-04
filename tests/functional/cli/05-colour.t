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
#-------------------------------------------------------------------------------

# Test that CLI colour output is disabled if output is not to a terminal.
# Uses the "script" command to make stdout log file look like a terminal.

. "$(dirname "$0")/test_header"
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    skip_all "Tests not compatibile with $OSTYPE"
fi
set_test_number 7

ANSI='\e\['

# No redirection.
script -q -c "cylc scan -t rich" log > /dev/null 2>&1
grep_ok "$ANSI" log -P  # color

# FIXME: this test doesn't work because the output includes a color reset char
# at the end for some reason: https://github.com/cylc/cylc-flow/issues/6467
# script -q -c "cylc scan -t rich --color=never" log > /dev/null 2>&1
# grep_fail "$ANSI" log -P  # no color

# Redirected.
cylc scan -t rich > log
grep_fail "$ANSI" log -P  # no color

cylc scan -t rich --color=always > log
grep_ok "$ANSI" log -P  # color

# Check command help too (gets printed during command line parsing).

# No redirection.
script -q -c "cylc scan --help" log > /dev/null 2>&1
grep_ok "$ANSI" log -P  # color

script -q -c "cylc scan --help --color never" log > /dev/null 2>&1
grep_fail "$ANSI" log -P  # no color

# Redirected.
cylc scan --help > log
grep_fail "$ANSI" log -P  # no color

cylc scan --help --color=always > log
grep_ok "$ANSI" log -P  # color
