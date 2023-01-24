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
# Test `cylc vip` (Validate Install Play)

. "$(dirname "$0")/test_header"
set_test_number 5

WORKFLOW_NAME="cylctb-x$(< /dev/urandom tr -dc _A-Z-a-z-0-9 | head -c6)"

cp -r "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/flow.cylc" .
cp -r "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/reference.log" .

run_ok "${TEST_NAME_BASE}-from-path" \
    cylc vip --no-detach --debug \
    --workflow-name "${WORKFLOW_NAME}" \
    --initial-cycle-point=1300 \
    --run-name sardine \
    --reference-test

grep_ok "13000101T0000Z" "${TEST_NAME_BASE}-from-path.stdout"

grep "\$" "${TEST_NAME_BASE}-from-path.stdout" > VIPOUT.txt

named_grep_ok "${TEST_NAME_BASE}-it-validated" "$ cylc validate" "VIPOUT.txt"
named_grep_ok "${TEST_NAME_BASE}-it-installed" "$ cylc install" "VIPOUT.txt"
named_grep_ok "${TEST_NAME_BASE}-it-played" "$ cylc play" "VIPOUT.txt"

purge
exit 0
