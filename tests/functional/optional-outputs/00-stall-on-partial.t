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

# Check that partially satisfied prerequisites count toward runahead limit.
. "$(dirname "$0")/test_header"
set_test_number 5

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"

workflow_run_fail "${TEST_NAME_BASE}-run" \
    cylc play -n --reference-test --debug "${WORKFLOW_NAME}"

LOG="${WORKFLOW_RUN_DIR}/log/scheduler/log"
grep_ok "Partially satisfied prerequisites" "${LOG}"
grep_ok "1/bar is waiting on \['1/foo:y'\]" "${LOG}"
grep_ok "Workflow stalled" "${LOG}"

purge
exit
