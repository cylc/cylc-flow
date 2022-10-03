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
# Test workflow event handler, dump unmet prereqs on stall
. "$(dirname "$0")/test_header"
set_test_number 9

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" \
    cylc validate "${WORKFLOW_NAME}"

workflow_run_fail "${TEST_NAME_BASE}-run" \
    cylc play --reference-test --debug --no-detach "${WORKFLOW_NAME}"

grep_ok '"abort on stall timeout" is set' "${TEST_NAME_BASE}-run.stderr"

grep_ok "ERROR - Incomplete tasks:" "${TEST_NAME_BASE}-run.stderr"

grep_ok "1/foo did not complete required outputs: \['succeeded'\]" \
    "${TEST_NAME_BASE}-run.stderr"

grep_ok "WARNING - Partially satisfied prerequisites:" \
    "${TEST_NAME_BASE}-run.stderr"

grep_ok "1/f_1 is waiting on \['1/foo:succeeded'\]" \
    "${TEST_NAME_BASE}-run.stderr"

grep_ok "1/f_2 is waiting on \['1/foo:succeeded'\]" \
    "${TEST_NAME_BASE}-run.stderr"

grep_ok "1/f_3 is waiting on \['1/foo:succeeded'\]" \
    "${TEST_NAME_BASE}-run.stderr"

purge
exit
