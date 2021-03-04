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
#------------------------------------------------------------------------

# test the output of `cylc play` with different `--format` options

. "$(dirname "$0")/test_header"

set_test_number 8

init_suite "${TEST_NAME_BASE}" <<'__FLOW_CONFIG__'
[scheduler]
    allow implicit tasks = True
[scheduling]
    [[dependencies]]
        R1 = foo
__FLOW_CONFIG__

TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${SUITE_NAME}"

# format=plain
TEST_NAME="${TEST_NAME_BASE}-run-format-plain"
suite_run_ok "${TEST_NAME}" cylc play --format plain "${SUITE_NAME}"
grep_ok 'listening on tcp:' "${TEST_NAME}.stdout"
grep_ok 'publishing on tcp:' "${TEST_NAME}.stdout"
grep_ok 'To view suite server program contact information:' \
    "${TEST_NAME}.stdout"
grep_ok 'Other ways to see if the suite is still running:' \
    "${TEST_NAME}.stdout"
poll_suite_stopped

delete_db

# format=json
TEST_NAME="${TEST_NAME_BASE}-run-format-json"
suite_run_ok "${TEST_NAME}" cylc play --format json "${SUITE_NAME}"
run_ok "${TEST_NAME}-fields" python3 -c '
import json
import sys
data = json.load(open(sys.argv[1], "r"))
print(list(sorted(data)), file=sys.stderr)
assert list(sorted(data)) == [
    "host", "pid", "ps_opts", "pub_url", "suite", "url"]
' "${TEST_NAME}.stdout"
poll_suite_stopped

purge
