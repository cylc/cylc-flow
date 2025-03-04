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
export REQUIRE_PLATFORM="loc:remote fs:indep comms:?(tcp|ssh)"
. "$(dirname "$0")/test_header"
set_test_number 3
#-------------------------------------------------------------------------------
# It should retry job log retrieval even if all hosts are not contactable.
#-------------------------------------------------------------------------------

init_workflow "${TEST_NAME_BASE}-1" <<__FLOW_CONFIG__
[scheduling]
    [[graph]]
        R1 = """
            remote
        """

[runtime]
    [[remote]]
        # script = sleep 1
        platform = ${CYLC_TEST_PLATFORM}
__FLOW_CONFIG__

# configure job retries on the test platform
create_test_global_config '' "
[platforms]
    [[${CYLC_TEST_PLATFORM}]]
        retrieve job logs = True
        retrieve job logs retry delays = 3*PT1S
        retrieve job logs command = fido
"

# * redirect retrieval attempts to a file where we can inspect them later
# * make it look like retrieval failed due to network issues (255 ret code)
JOB_LOG_RETR_CMD="${WORKFLOW_RUN_DIR}/bin/fido"
RETRIEVAL_ATTEMPT_LOG="${WORKFLOW_RUN_DIR}/retrieval-attempt-log"
mkdir "${WORKFLOW_RUN_DIR}/bin"
cat > "${WORKFLOW_RUN_DIR}/bin/fido" <<__HERE__
#!/usr/bin/env bash
echo "$@" >> "${RETRIEVAL_ATTEMPT_LOG}"
exit 255
__HERE__
chmod +x "${JOB_LOG_RETR_CMD}"

workflow_run_ok "${TEST_NAME_BASE}-play" \
    cylc play --debug --no-detach "${WORKFLOW_NAME}"

# it should try retrieval three times
# Note: it should reset bad_hosts to allow retries to happen
TEST_NAME="${TEST_NAME_BASE}-retrieve-attempts"
# shellcheck disable=SC2002
# (cat'ting into pipe to avoid having to sed out the filename)
if [[ $(cat "${RETRIEVAL_ATTEMPT_LOG}" | wc -l) -eq 3 ]]; then
    ok "${TEST_NAME}"
else
    fail "${TEST_NAME}"
fi

# then fail once the retries have been exhausted
grep_workflow_log_ok "${TEST_NAME_BASE}-retrieve-fail" \
    'job-logs-retrieve for task event:succeeded failed'

purge
