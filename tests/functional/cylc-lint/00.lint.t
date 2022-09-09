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
set_test_number 18

cat > flow.cylc <<__HERE__
# This is definitely not an OK flow.cylc file.
[cylc]
   [[parameters]]
__HERE__

rm etc/global.cylc

TEST_NAME="${TEST_NAME_BASE}.vanilla"
run_ok "${TEST_NAME}" cylc lint .
named_grep_ok "check-for-error-code" "S004" "${TEST_NAME}.stdout"

TEST_NAME="${TEST_NAME_BASE}.pick-a-ruleset"
run_ok "${TEST_NAME}" cylc lint . -r 728
named_grep_ok "check-for-error-code" "U024" "${TEST_NAME}.stdout"

TEST_NAME="${TEST_NAME_BASE}.inplace"
run_ok "${TEST_NAME}" cylc lint . -i
named_grep_ok "check-for-error-code-in-file" "U024" flow.cylc

rm flow.cylc

cat > suite.rc <<__HERE__
# This is definitely not an OK flow.cylc file.
{{FOO}}
__HERE__

TEST_NAME="${TEST_NAME_BASE}.pick-a-ruleset"
run_ok "${TEST_NAME}" cylc lint . -r 728
named_grep_ok "do-not-upgrade-check-if-compat-mode" "Lint after renaming" "${TEST_NAME}.stderr"

TEST_NAME="${TEST_NAME_BASE}.pick-a-ruleset2"
run_ok "${TEST_NAME}" cylc lint . -r all

rm suite.rc

cat > flow.cylc <<__HERE__
# This one is fine
[scheduler]
__HERE__

TEST_NAME="${TEST_NAME_BASE}.zero-issues"
run_ok "${TEST_NAME}" cylc lint .
named_grep_ok "message on no errors" "found no issues" "${TEST_NAME}.stdout"

# It returns an error message if you attempt to lint a non-existant location
TEST_NAME="it-fails-if-not-target"
run_fail ${TEST_NAME} cylc lint "a-$(uuidgen)"
grep_ok "Workflow ID not found" "${TEST_NAME}.stderr"

# It returns a reference in reference mode
TEST_NAME="it-returns-a-reference"
run_ok "${TEST_NAME}" cylc lint --list-codes
named_grep_ok "${TEST_NAME}-contains-style-codes" "^S001:" "${TEST_NAME}.stdout"
TEST_NAME="it-returns-a-reference-style"
run_ok "${TEST_NAME}" cylc lint --list-codes -r 'style'
named_grep_ok "${TEST_NAME}-contains-style-codes" "^S001:" "${TEST_NAME}.stdout"
grep_fail "^U" "${TEST_NAME}.stdout"


rm flow.cylc
