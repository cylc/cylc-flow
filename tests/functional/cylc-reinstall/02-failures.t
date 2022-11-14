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
# Test workflow reinstallation expected failures
. "$(dirname "$0")/test_header"
set_test_number 23

# Test fail no workflow run dir

TEST_NAME="${TEST_NAME_BASE}-reinstall-no-run-dir"
make_rnd_workflow
run_ok "${TEST_NAME}-install" cylc install "${RND_WORKFLOW_SOURCE}" --workflow-name="${RND_WORKFLOW_NAME}" --no-run-name
rm -rf "${RND_WORKFLOW_RUNDIR}"
run_fail "${TEST_NAME}-reinstall" cylc reinstall "${RND_WORKFLOW_NAME}"
cmp_ok "${TEST_NAME}-reinstall.stderr" <<__ERR__
InputError: Workflow ID not found: ${RND_WORKFLOW_RUNDIR#*/cylc-run/}
(Directory not found: ${RND_WORKFLOW_RUNDIR})
__ERR__
purge_rnd_workflow

# Test fail no workflow source dir

TEST_NAME="${TEST_NAME_BASE}-reinstall-no-source-dir"
make_rnd_workflow
run_ok "${TEST_NAME}-install" cylc install "${RND_WORKFLOW_SOURCE}" --workflow-name="${RND_WORKFLOW_NAME}" --no-run-name
rm -rf "${RND_WORKFLOW_SOURCE}"
run_fail "${TEST_NAME}-reinstall" cylc reinstall "${RND_WORKFLOW_NAME}"
cmp_ok "${TEST_NAME}-reinstall.stderr" <<__ERR__
WorkflowFilesError: Workflow source dir is not accessible: "${RND_WORKFLOW_SOURCE}".
Restore the source or modify the "${RND_WORKFLOW_RUNDIR}/_cylc-install/source" symlink to continue.
__ERR__
purge_rnd_workflow

# Test fail no flow.cylc or suite.rc file

TEST_NAME="${TEST_NAME_BASE}-no-flow-file"
make_rnd_workflow
run_ok "${TEST_NAME}-install" cylc install "${RND_WORKFLOW_SOURCE}" --workflow-name="${RND_WORKFLOW_NAME}" --no-run-name
rm -f "${RND_WORKFLOW_SOURCE}/flow.cylc"
run_fail "${TEST_NAME}" cylc reinstall "${RND_WORKFLOW_NAME}"
cmp_ok "${TEST_NAME}.stderr" <<__ERR__
WorkflowFilesError: No flow.cylc or suite.rc in ${RND_WORKFLOW_SOURCE}
__ERR__
purge_rnd_workflow

# Test fail both flow.cylc and suite.rc file

TEST_NAME="${TEST_NAME_BASE}-both-flow-and-suite-file"
make_rnd_workflow
run_ok "${TEST_NAME}-install" cylc install "${RND_WORKFLOW_SOURCE}" --workflow-name="${RND_WORKFLOW_NAME}" --no-run-name
touch "${RND_WORKFLOW_SOURCE}/suite.rc"
run_fail "${TEST_NAME}" cylc reinstall "${RND_WORKFLOW_NAME}"
cmp_ok "${TEST_NAME}.stderr" <<__ERR__
WorkflowFilesError: Both flow.cylc and suite.rc files are present in ${RND_WORKFLOW_SOURCE}. \
Please remove one and try again. For more information visit: \
https://cylc.github.io/cylc-doc/stable/html/7-to-8/summary.html#backward-compatibility
__ERR__
purge_rnd_workflow

# Test source dir can not contain '_cylc-install, log, share, work' dirs for cylc reinstall

for DIR in 'work' 'share' 'log' '_cylc-install'; do
    TEST_NAME="${TEST_NAME_BASE}-${DIR}-forbidden-in-source"
    make_rnd_workflow
    pushd "${RND_WORKFLOW_SOURCE}" || exit 1
    cylc install --no-run-name --workflow-name="${RND_WORKFLOW_NAME}"
    mkdir ${DIR}
    run_fail "${TEST_NAME}" cylc reinstall "${RND_WORKFLOW_NAME}"
    cmp_ok "${TEST_NAME}.stderr" <<__ERR__
WorkflowFilesError: ${RND_WORKFLOW_NAME} installation failed - ${DIR} exists in source directory.
__ERR__
    purge_rnd_workflow
    popd || exit 1
done

# Test cylc reinstall raises error when no source dir.
TEST_NAME="${TEST_NAME_BASE}-reinstall-no-source-raises-error"
make_rnd_workflow
pushd "${RND_WORKFLOW_SOURCE}" || exit 1
run_ok "${TEST_NAME}-install" cylc install --no-run-name --workflow-name="${RND_WORKFLOW_NAME}"
pushd "${RND_WORKFLOW_RUNDIR}" || exit 1
rm -rf "_cylc-install"
run_fail "${TEST_NAME}-reinstall" cylc reinstall "$RND_WORKFLOW_NAME"
cmp_ok "${TEST_NAME}-reinstall.stderr" <<__ERR__
WorkflowFilesError: "${RND_WORKFLOW_NAME}" was not installed with cylc install.
__ERR__
popd || exit 1
popd || exit 1
purge_rnd_workflow

exit
