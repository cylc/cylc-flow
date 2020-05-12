#!/bin/bash
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

set_test_number 16

# Configure a fake editor that just copies a job file to ${DESTFILE}.
create_test_globalrc '' '
[editors]
    terminal = my-editor
    gui = my-editor'

function run_tests {
    HOST=$1
    OWNER=$2

    TEST_NAME="${TEST_NAME_BASE}-validate"
    run_ok "${TEST_NAME}" cylc validate --set="CYLC_TEST_HOST=$HOST" \
       --set="CYLC_TEST_OWNER=$OWNER" "${SUITE_NAME}"

    # Run the suite to generate some log files.
    TEST_NAME="${TEST_NAME_BASE}-suite-run"
    run_ok "${TEST_NAME}" cylc run --set="CYLC_TEST_HOST=$HOST" \
       --set="CYLC_TEST_OWNER=$OWNER" --no-detach "${SUITE_NAME}"

    LOG_DIR="$RUN_DIR/${SUITE_NAME}"
    JOB_LOG_DIR="${LOG_DIR}/log/job/1/foo/01"

    for JOBFILE in "job" "job.out" "job.err" "job.status" "job-activity.log" \
          "job.custom"; do
        export DESTFILE="${JOBFILE}.edit"
        export ORIGFILE="${JOBFILE}.orig"
        # Check we can view the job log file in the "editor".
        TEST_NAME="${TEST_NAME_BASE}-${JOBFILE}"
        run_ok "${TEST_NAME}" cylc cat-log -f "${JOBFILE}" -m e "${SUITE_NAME}" foo.1
        # Compare viewed (i.e. copied by the fake editor) file with the original.
        # (The original must be catted as it could be a remote log file).
        cylc cat-log -f "${JOBFILE}" -m c "${SUITE_NAME}" foo.1 > "${ORIGFILE}"
        cmp_ok "${DESTFILE}" "${ORIGFILE}"
    done

    # Finally, test --geditor on the 'job' file.
    TEST_NAME="${TEST_NAME_BASE}-job"
    JOBFILE="job"
    export DESTFILE="${JOBFILE}.edit"
    run_ok "${TEST_NAME}" cylc cat-log -m e --geditor -f j "${SUITE_NAME}" foo.1
    cmp_ok "${DESTFILE}" "${JOB_LOG_DIR}/${JOBFILE}"
}
