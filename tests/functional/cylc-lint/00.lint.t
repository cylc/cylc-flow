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
set_test_number 12

cat > flow.cylc <<__HERE__
# This is definately not an OK flow.cylc file.
{{FOO}}
__HERE__

TEST_NAME="${TEST_NAME_BASE}.vanilla"
run_ok "${TEST_NAME}" cylc lint
named_grep_ok "check-for-error-code" "U038" "${TEST_NAME}.stdout"

TEST_NAME="${TEST_NAME_BASE}.pick-a-ruleset"
run_ok "${TEST_NAME}" cylc lint . -r 728
named_grep_ok "check-for-error-code" "U038" "${TEST_NAME}.stdout"

TEST_NAME="${TEST_NAME_BASE}.inplace"
run_ok "${TEST_NAME}" cylc lint . -i
named_grep_ok "check-for-error-code-in-file" "U038" flow.cylc

rm flow.cylc

cat > suite.rc <<__HERE__
# This is definately not an OK flow.cylc file.
{{FOO}}
__HERE__

TEST_NAME="${TEST_NAME_BASE}.pick-a-ruleset"
run_ok "${TEST_NAME}" cylc lint . -r 728
named_grep_ok "do-not-upgrade-check-if-compat-mode" "No checks" "${TEST_NAME}.stderr"

TEST_NAME="${TEST_NAME_BASE}.pick-a-ruleset2"
run_ok "${TEST_NAME}" cylc lint .
named_grep_ok "do-not-upgrade-check-if-compat-mode2" "only for style" "${TEST_NAME}.stderr"

rm suite.rc
rm etc/global.cylc

cat > flow.cylc <<__HERE__
# This one is fine
[scheduler]
__HERE__

TEST_NAME="${TEST_NAME_BASE}.zero-issues"
run_ok "${TEST_NAME}" cylc lint
named_grep_ok "message on no errors" "found 0 issues" "${TEST_NAME}.stdout"

rm flow.cylc
