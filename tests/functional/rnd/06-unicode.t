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

# Ensure that UnicodeDecodeError's are caught and handled elegantly
# See: https://github.com/cylc/cylc-flow/pull/4947

. "$(dirname "$0")/test_header"
if [[ -n ${CI:-} ]]; then
    # test requires a real terminal to write to
    skip_all
fi
set_test_number 4

# this command should work where UTF-8 is supported
run_ok "${TEST_NAME_BASE}-good" env LANG=en_GB.UTF-8 cylc scan --help

# but fail where it is not
run_fail "${TEST_NAME_BASE}-bad" env LANG=en_GB cylc scan --help

# we should raise a sensible error message
grep_ok \
    'A UTF-8 compatible terminal is required for this command' \
    "${TEST_NAME_BASE}-bad.stderr"

# and provide some helpful advice
grep_ok \
    'LANG=C.UTF-8 cylc scan --help' \
    "${TEST_NAME_BASE}-bad.stderr"

exit
