#!/bin/bash
#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 NIWA
#C:
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.
#-------------------------------------------------------------------------------
# Test that global config is used search for poll
. "$(dirname "${0}")/test_header"
#-------------------------------------------------------------------------------
set_test_number 7
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
#-------------------------------------------------------------------------------
run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
export CYLC_CONF_PATH="${PWD}/conf"
suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --reference-test --debug "${SUITE_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}"
SUITE_RUN_DIR="$(cylc get-global-config --print-run-dir)/${SUITE_NAME}"
JOB_FILE="${SUITE_RUN_DIR}/log/job/1/foo/NN/job"
run_ok "job" grep -q "CYLC_TASK_COMMS_METHOD=poll" "${JOB_FILE}"
run_ok "job" grep -q "CYLC_TASK_MSG_RETRY_INTVL=9.0" "${JOB_FILE}"
run_ok "job" grep -q "CYLC_TASK_MSG_TIMEOUT=20.0" "${JOB_FILE}"
LOG_FILE="${SUITE_RUN_DIR}/log/suite/log"
run_ok "log" grep -q "using default submission polling intervals" "${LOG_FILE}"
run_ok "log" grep -q "using default execution polling intervals" "${LOG_FILE}"
#-------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"
exit
