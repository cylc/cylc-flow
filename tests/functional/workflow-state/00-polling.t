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
# Validate and run the workflow-state/polling test workflow
# The test workflow is in polling/; it depends on another workflow in upstream/

. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 7
#-------------------------------------------------------------------------------
install_workflow "${TEST_NAME_BASE}" 'polling'
#-------------------------------------------------------------------------------
# copy the upstream workflow to the test directory and install it
cp -r "${TEST_SOURCE_DIR}/upstream" "${TEST_DIR}/"
# use full range of characters in the workflow-to-be-polled name:
UPSTREAM="${WORKFLOW_NAME}-up_stre.am"
cylc install  "${TEST_DIR}/upstream" --workflow-name="${UPSTREAM}" --no-run-name
#-------------------------------------------------------------------------------
# validate both workflows as tests
TEST_NAME="${TEST_NAME_BASE}-validate-upstream"
run_ok "${TEST_NAME}" cylc validate --debug "${UPSTREAM}"

TEST_NAME=${TEST_NAME_BASE}-validate-polling-y
run_fail "${TEST_NAME}" \
    cylc validate --set="UPSTREAM='${UPSTREAM}'" --set="OUTPUT=':y'" "${WORKFLOW_NAME}"

contains_ok "${TEST_NAME}.stderr" <<__ERR__
WorkflowConfigError: Polling task "l-mess" must configure a target status or output message in \
the graph (:y) or task definition (message = "the quick brown fox") but not both.
__ERR__

TEST_NAME=${TEST_NAME_BASE}-validate-polling
run_ok "${TEST_NAME}" \
    cylc validate --debug --set="UPSTREAM='${UPSTREAM}'" "${WORKFLOW_NAME}"

#-------------------------------------------------------------------------------
# run the upstream workflow and detach (not a test)
cylc play "${UPSTREAM}"

#-------------------------------------------------------------------------------
# check auto-generated task script for lbad
cylc config -d \
    --set="UPSTREAM='${UPSTREAM}'" -i '[runtime][lbad]script' "${WORKFLOW_NAME}" \
    >'lbad.script'
cmp_ok 'lbad.script' << __END__
echo cylc workflow-state ${UPSTREAM}//\$CYLC_TASK_CYCLE_POINT/bad:failed --interval=2 --max-polls=20
cylc workflow-state ${UPSTREAM}//\$CYLC_TASK_CYCLE_POINT/bad:failed --interval=2 --max-polls=20
__END__

# check auto-generated task script for l-good
cylc config -d \
    --set="UPSTREAM='${UPSTREAM}'" -i '[runtime][l-good]script' "${WORKFLOW_NAME}" \
    >'l-good.script'
cmp_ok 'l-good.script' << __END__
echo cylc workflow-state ${UPSTREAM}//\$CYLC_TASK_CYCLE_POINT/good-stuff:succeeded --interval=2 --max-polls=20
cylc workflow-state ${UPSTREAM}//\$CYLC_TASK_CYCLE_POINT/good-stuff:succeeded --interval=2 --max-polls=20
__END__

#-------------------------------------------------------------------------------
# run the workflow-state polling test workflow
TEST_NAME="${TEST_NAME_BASE}-run"
workflow_run_ok "${TEST_NAME}" \
    cylc play --reference-test --debug --no-detach \
    --set="UPSTREAM='${UPSTREAM}'" "${WORKFLOW_NAME}"

#-------------------------------------------------------------------------------
purge

#-------------------------------------------------------------------------------
# clean up the upstream workflow
# just in case (expect error message here, but exit 0):
cylc stop --now "${UPSTREAM}" --max-polls=20 --interval=2 >'/dev/null' 2>&1
purge "${UPSTREAM}"
exit
