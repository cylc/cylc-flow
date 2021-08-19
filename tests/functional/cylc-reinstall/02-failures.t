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

# Test fail no workflow source dir

TEST_NAME="${TEST_NAME_BASE}-reinstall-no-run-dir"
make_rnd_workflow
run_ok "${TEST_NAME}-install" cylc install -C "${RND_WORKFLOW_SOURCE}" --flow-name="${RND_WORKFLOW_NAME}" --no-run-name
rm -rf "${RND_WORKFLOW_RUNDIR}"
run_fail "${TEST_NAME}-reinstall" cylc reinstall "${RND_WORKFLOW_NAME}"
cmp_ok "${TEST_NAME}-reinstall.stderr" <<__ERR__
WorkflowFilesError: "${RND_WORKFLOW_NAME}" is not an installed workflow.
__ERR__
purge_rnd_workflow

# Test fail no workflow source dir

TEST_NAME="${TEST_NAME_BASE}-reinstall-no-source-dir"
make_rnd_workflow
run_ok "${TEST_NAME}-install" cylc install -C "${RND_WORKFLOW_SOURCE}" --flow-name="${RND_WORKFLOW_NAME}" --no-run-name
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
run_ok "${TEST_NAME}-install" cylc install -C "${RND_WORKFLOW_SOURCE}" --flow-name="${RND_WORKFLOW_NAME}" --no-run-name
rm -f "${RND_WORKFLOW_SOURCE}/flow.cylc"
run_fail "${TEST_NAME}" cylc reinstall "${RND_WORKFLOW_NAME}"
cmp_ok "${TEST_NAME}.stderr" <<__ERR__
WorkflowFilesError: no flow.cylc or suite.rc in ${RND_WORKFLOW_SOURCE}
__ERR__
purge_rnd_workflow

# Test source dir can not contain '_cylc-install, log, share, work' dirs for cylc reinstall

for DIR in 'work' 'share' 'log' '_cylc-install'; do
    TEST_NAME="${TEST_NAME_BASE}-${DIR}-forbidden-in-source"
    make_rnd_workflow
    pushd "${RND_WORKFLOW_SOURCE}" || exit 1
    cylc install --no-run-name --flow-name="${RND_WORKFLOW_NAME}"
    mkdir ${DIR}
    run_fail "${TEST_NAME}" cylc reinstall "${RND_WORKFLOW_NAME}"
    cmp_ok "${TEST_NAME}.stderr" <<__ERR__
WorkflowFilesError: ${RND_WORKFLOW_NAME} installation failed. - ${DIR} exists in source directory.
__ERR__
    purge_rnd_workflow
    popd || exit 1
done

# Test cylc reinstall (no args given) raises error when no source dir.
TEST_NAME="${TEST_NAME_BASE}-reinstall-no-source-rasies-error"
make_rnd_workflow
pushd "${RND_WORKFLOW_SOURCE}" || exit 1
run_ok "${TEST_NAME}-install" cylc install --no-run-name --flow-name="${RND_WORKFLOW_NAME}"
pushd "${RND_WORKFLOW_RUNDIR}" || exit 1
rm -rf "_cylc-install"
run_fail "${TEST_NAME}-reinstall" cylc reinstall
cmp_ok "${TEST_NAME}-reinstall.stderr" <<__ERR__
WorkflowFilesError: "${RND_WORKFLOW_NAME}" was not installed with cylc install.
__ERR__
popd || exit 1
popd || exit 1
purge_rnd_workflow

# Test cylc reinstall (args given) raises error when no source dir.
TEST_NAME="${TEST_NAME_BASE}-reinstall-no-source-rasies-error2"
make_rnd_workflow
pushd "${RND_WORKFLOW_SOURCE}" || exit 1
run_ok "${TEST_NAME}-install" cylc install --no-run-name --flow-name="${RND_WORKFLOW_NAME}"
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
