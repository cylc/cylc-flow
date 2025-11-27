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

#------------------------------------------------------------------------------
# Test workflow installation
. "$(dirname "$0")/test_header"
set_test_number 20

cat > flow.cylc <<__HERE__
# This is definitely not an OK flow.cylc file.
[cylc]
   [[parameters]]
__HERE__

rm etc/global.cylc

TEST_NAME="${TEST_NAME_BASE}.vanilla"
run_fail "${TEST_NAME}" cylc lint .
named_grep_ok "${TEST_NAME_BASE}-check-for-error-code" "S004" "${TEST_NAME}.stdout"

TEST_NAME="${TEST_NAME_BASE}.pick-a-ruleset"
run_fail "${TEST_NAME}" cylc lint . -r 728
named_grep_ok "${TEST_NAME_BASE}-check-for-error-code" "U998" "${TEST_NAME}.stdout"

TEST_NAME="${TEST_NAME_BASE}.inplace"
run_fail "${TEST_NAME}" cylc lint . -i
named_grep_ok "${TEST_NAME_BASE}-check-for-error-code-in-file" "U998" flow.cylc

rm flow.cylc

cat > suite.rc <<__HERE__
# This is definitely not an OK flow.cylc file.
{{FOO}}
__HERE__

TEST_NAME="${TEST_NAME_BASE}.pick-a-ruleset-728"
run_fail "${TEST_NAME}" cylc lint . -r 728
named_grep_ok "${TEST_NAME_BASE}-do-not-upgrade-check-if-compat-mode" "Lint after renaming" "${TEST_NAME}.stderr"

TEST_NAME="${TEST_NAME_BASE}.pick-a-ruleset-728-exit-zero"
run_ok "${TEST_NAME}" cylc lint . -r 728 --exit-zero

TEST_NAME="${TEST_NAME_BASE}.pick-a-ruleset-all"
run_fail "${TEST_NAME}" cylc lint . -r all

TEST_NAME="${TEST_NAME_BASE}.exit-zero"
run_ok "${TEST_NAME}" cylc lint --exit-zero .

rm suite.rc

cat > flow.cylc <<__HERE__
# This one is fine
[scheduler]
__HERE__

TEST_NAME="${TEST_NAME_BASE}.zero-issues"
run_ok "${TEST_NAME}" cylc lint .
named_grep_ok "${TEST_NAME_BASE}-message-on-no-errors" "found no issues" "${TEST_NAME}.stdout"

# It returns an error message if you attempt to lint a non-existant location
TEST_NAME="it-fails-if-not-target"
run_fail "${TEST_NAME}" cylc lint "a-$(uuidgen)"
grep_ok "Workflow ID not found" "${TEST_NAME}.stderr"

# It returns a reference in reference mode
TEST_NAME="${TEST_NAME_BASE}-it-returns-a-reference"
run_ok "${TEST_NAME}" cylc lint --list-codes
named_grep_ok "${TEST_NAME}-contains-style-codes" "^S001:" "${TEST_NAME}.stdout"
TEST_NAME="it-returns-a-reference-style"
run_ok "${TEST_NAME}" cylc lint --list-codes -r 'style'
named_grep_ok "${TEST_NAME}-contains-style-codes" "^S001:" "${TEST_NAME}.stdout"
grep_fail "^U" "${TEST_NAME}.stdout"


rm flow.cylc
