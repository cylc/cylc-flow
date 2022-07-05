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
# Test workflow re-installation
. "$(dirname "$0")/test_header"
set_test_number 17

# Test basic cylc reinstall, named run given
TEST_NAME="${TEST_NAME_BASE}-basic-named-run"
make_rnd_workflow
pushd "${RND_WORKFLOW_SOURCE}" || exit 1
run_ok "${TEST_NAME}" cylc install
cmp_ok "${TEST_NAME}.stdout" <<__OUT__
INSTALLED $RND_WORKFLOW_NAME/run1 from ${RND_WORKFLOW_SOURCE}
__OUT__
run_ok "basic-reinstall" cylc reinstall "${RND_WORKFLOW_NAME}/run1"
REINSTALL_LOG="$(find "${RND_WORKFLOW_RUNDIR}/run1/log/install" -type f -name '*reinstall.log')"
grep_ok "REINSTALLED ${RND_WORKFLOW_NAME}/run1 from ${RND_WORKFLOW_SOURCE}" "${REINSTALL_LOG}"

popd || exit 1
purge_rnd_workflow

#------------------------------------------------------------------------------
# Test install/reinstall executed from elsewhere in filesystem
TEST_NAME="${TEST_NAME_BASE}-named-flow"
make_rnd_workflow
pushd "${TMPDIR}" || exit 1
run_ok "${TEST_NAME}-install" cylc install "${RND_WORKFLOW_SOURCE}" --workflow-name="${RND_WORKFLOW_NAME}"
cmp_ok "${TEST_NAME}-install.stdout" <<__OUT__
INSTALLED ${RND_WORKFLOW_NAME}/run1 from ${RND_WORKFLOW_SOURCE}
__OUT__
run_ok "${TEST_NAME}-reinstall" cylc reinstall "${RND_WORKFLOW_NAME}/run1"
cmp_ok "${TEST_NAME}-reinstall.stdout" <<__OUT__
REINSTALLED $RND_WORKFLOW_NAME/run1 from ${RND_WORKFLOW_SOURCE}
__OUT__
popd || exit 1
purge_rnd_workflow
rm -rf "${RUN_DIR:?}/${RND_WORKFLOW_NAME}/"

#------------------------------------------------------------------------------
# Test cylc reinstall succeeds if suite.rc file in source dir
TEST_NAME="${TEST_NAME_BASE}-no-flow-file"
make_rnd_workflow
rm -f "${RND_WORKFLOW_SOURCE}/flow.cylc"
touch "${RND_WORKFLOW_SOURCE}/suite.rc"
run_ok "${TEST_NAME}" cylc install "${RND_WORKFLOW_SOURCE}" --workflow-name="${RND_WORKFLOW_NAME}"
cmp_ok "${TEST_NAME}.stdout" <<__OUT__
INSTALLED $RND_WORKFLOW_NAME/run1 from ${RND_WORKFLOW_SOURCE}
__OUT__

run_ok "${TEST_NAME}-reinstall" cylc reinstall "${RND_WORKFLOW_NAME}/run1"
purge_rnd_workflow

#------------------------------------------------------------------------------
# Test --dry-run
TEST_NAME="${TEST_NAME_BASE}-dry-run"
make_rnd_workflow
touch "${RND_WORKFLOW_SOURCE}/a"
touch "${RND_WORKFLOW_SOURCE}/b"
touch "${RND_WORKFLOW_SOURCE}/rose-suite.conf"
run_ok "${TEST_NAME}" \
    cylc install "${RND_WORKFLOW_SOURCE}" \
    --workflow-name="${RND_WORKFLOW_NAME}" --no-run-name
rm "${RND_WORKFLOW_SOURCE}/a"
touch "${RND_WORKFLOW_SOURCE}/c"
# make sure the install log was created
RUN_DIR="${HOME}/cylc-run/${RND_WORKFLOW_NAME}"
if [[ "$(ls -1 "${RUN_DIR}/log/install"/* | wc -w)" == 1 ]]
then
    ok "${TEST_NAME}-log"
else
    fail "${TEST_NAME}-log"
fi
run_ok "${TEST_NAME}" \
    cylc reinstall "${RND_WORKFLOW_NAME}" \
    --dry-run --color=never
# the dry run output should go to stderr
cmp_ok "${TEST_NAME}.stderr" <<__OUT__
NOTE: Files created by Rose file installation will show as deleted.
      They will be re-created during the reinstall process.
del. a
send c
__OUT__
# make sure that rsync was indeed run in dry mode!
if [[ -f "${RUN_DIR}/c" ]]; then
    fail "${TEST_NAME}-transfer"
else
    ok "${TEST_NAME}-transfer"
fi
# make sure no reinstall log file was created
if [[ "$(ls -1 "${RUN_DIR}/log/install"/* | wc -w)" == 1 ]]
then
    ok "${TEST_NAME}-log"
else
    fail "${TEST_NAME}-log"
fi


exit
