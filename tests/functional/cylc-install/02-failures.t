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
# Test workflow installation failures


. "$(dirname "$0")/test_header"
set_test_number 39

# Test source directory between runs that are not consistent result in error

TEST_NAME="${TEST_NAME_BASE}-forbid-inconsistent-source-dir-between-runs"
SOURCE_DIR_1="test-install-${CYLC_TEST_TIME_INIT}/${TEST_NAME_BASE}"
mkdir -p "${PWD}/${SOURCE_DIR_1}"
pushd "${SOURCE_DIR_1}" || exit 1
touch flow.cylc

run_ok "${TEST_NAME}" cylc install
popd || exit 1
SOURCE_DIR_2="test-install-${CYLC_TEST_TIME_INIT}2/${TEST_NAME_BASE}"
mkdir -p "${PWD}/${SOURCE_DIR_2}"
pushd "${SOURCE_DIR_2}" || exit 1
touch flow.cylc
run_fail "${TEST_NAME}" cylc install

contains_ok "${TEST_NAME}.stderr" <<__ERR__
WorkflowFilesError: Source directory not consistent between runs.
__ERR__
rm -rf "${PWD:?}/${SOURCE_DIR_1}" "${PWD:?}/${SOURCE_DIR_2}"
rm -rf "${RUN_DIR:?}/${TEST_NAME_BASE}"
popd || exit

# -----------------------------------------------------------------------------
# Test fail no flow.cylc or suite.rc file

make_rnd_workflow

TEST_NAME="${TEST_NAME_BASE}-no-flow-file"
rm -f "${RND_WORKFLOW_SOURCE}/flow.cylc"
run_fail "${TEST_NAME}" cylc install --flow-name="${RND_WORKFLOW_NAME}" -C "${RND_WORKFLOW_SOURCE}"
contains_ok "${TEST_NAME}.stderr" <<__ERR__
WorkflowFilesError: no flow.cylc or suite.rc in ${RND_WORKFLOW_SOURCE}
__ERR__

# Test fail no workflow source dir

TEST_NAME="${TEST_NAME_BASE}-nodir"
rm -rf "${RND_WORKFLOW_SOURCE}"
run_fail "${TEST_NAME}" cylc install --flow-name="${RND_WORKFLOW_NAME}" --no-run-name -C "${RND_WORKFLOW_SOURCE}"
contains_ok "${TEST_NAME}.stderr" <<__ERR__
WorkflowFilesError: no flow.cylc or suite.rc in ${RND_WORKFLOW_SOURCE}
__ERR__

purge_rnd_workflow

# -----------------------------------------------------------------------------
# Test cylc install fails when given flow-name that is an absolute path

make_rnd_workflow

TEST_NAME="${TEST_NAME_BASE}-no-abs-path-flow-name"
run_fail "${TEST_NAME}" cylc install --flow-name="${RND_WORKFLOW_SOURCE}" -C "${RND_WORKFLOW_SOURCE}"
contains_ok "${TEST_NAME}.stderr" <<__ERR__
WorkflowFilesError: workflow name cannot be an absolute path: ${RND_WORKFLOW_SOURCE}
__ERR__

# Test cylc install fails when given forbidden run-name

TEST_NAME="${TEST_NAME_BASE}-run-name-forbidden"
run_fail "${TEST_NAME}" cylc install --run-name=_cylc-install -C "${RND_WORKFLOW_SOURCE}"
contains_ok "${TEST_NAME}.stderr" <<__ERR__
WorkflowFilesError: Run name cannot be "_cylc-install".
__ERR__

# Test cylc install invalid flow-name

TEST_NAME="${TEST_NAME_BASE}-invalid-flow-name"
run_fail "${TEST_NAME}" cylc install --flow-name=".invalid" -C "${RND_WORKFLOW_SOURCE}"
contains_ok "${TEST_NAME}.stderr" <<__ERR__
WorkflowFilesError: invalid workflow name '.invalid' - cannot start with: \`\`.\`\`, \`\`-\`\`
__ERR__

# Test --run-name and --no-run-name options are mutually exclusive

TEST_NAME="${TEST_NAME_BASE}--no-run-name-and--run-name-forbidden"
pushd "${RND_WORKFLOW_SOURCE}" || exit 1
run_fail "${TEST_NAME}" cylc install --run-name="${RND_WORKFLOW_NAME}" --no-run-name
contains_ok "${TEST_NAME}.stderr" <<__ERR__
cylc: error: options --no-run-name and --run-name are mutually exclusive.
__ERR__
popd || exit 1

purge_rnd_workflow

# -----------------------------------------------------------------------------
# Test source dir can not contain '_cylc-install, log, share, work' dirs

for DIR in 'work' 'share' 'log' '_cylc-install'; do
    TEST_NAME="${TEST_NAME_BASE}-${DIR}-forbidden-in-source"
    make_rnd_workflow
    pushd "${RND_WORKFLOW_SOURCE}" || exit 1
    mkdir ${DIR}
    run_fail "${TEST_NAME}" cylc install
    contains_ok "${TEST_NAME}.stderr" <<__ERR__
WorkflowFilesError: ${RND_WORKFLOW_NAME} installation failed. - ${DIR} exists in source directory.
__ERR__
    purge_rnd_workflow
    popd || exit 1
done

# -----------------------------------------------------------------------------
# Test running cylc install twice, first using --run-name, followed by standard run results in error

TEST_NAME="${TEST_NAME_BASE}-install-twice-mix-options-1-1st-install"
make_rnd_workflow
pushd "${RND_WORKFLOW_SOURCE}" || exit 1
run_ok "${TEST_NAME}" cylc install --run-name=olaf
contains_ok "${TEST_NAME}.stdout" <<__OUT__
INSTALLED ${RND_WORKFLOW_NAME}/olaf from ${RND_WORKFLOW_SOURCE}
__OUT__
TEST_NAME="${TEST_NAME_BASE}-install-twice-mix-options-1-2nd-install"
run_fail "${TEST_NAME}" cylc install
contains_ok "${TEST_NAME}.stderr" <<__ERR__
WorkflowFilesError: This path: "${RND_WORKFLOW_RUNDIR}" contains an installed workflow. Try again, using --run-name.
__ERR__
popd || exit 1
purge_rnd_workflow

# -----------------------------------------------------------------------------
# Test running cylc install twice, first using standard run, followed by --run-name results in error

TEST_NAME="${TEST_NAME_BASE}-install-twice-mix-options-2-1st-install"
make_rnd_workflow
pushd "${RND_WORKFLOW_SOURCE}" || exit 1
run_ok "${TEST_NAME}" cylc install
contains_ok "${TEST_NAME}.stdout" <<__OUT__
INSTALLED ${RND_WORKFLOW_NAME}/run1 from ${RND_WORKFLOW_SOURCE}
__OUT__
TEST_NAME="${TEST_NAME_BASE}-install-twice-mix-options-2-2nd-install"
run_fail "${TEST_NAME}" cylc install --run-name=olaf
contains_ok "${TEST_NAME}.stderr" <<__ERR__
WorkflowFilesError: This path: "${RND_WORKFLOW_RUNDIR}" contains installed numbered runs. Try again, using cylc install without --run-name.
__ERR__
popd || exit 1
purge_rnd_workflow

# -----------------------------------------------------------------------------
# Test running cylc install twice, using the same --run-name results in error

TEST_NAME="${TEST_NAME_BASE}-install-twice-same-run-name-1st-install"
make_rnd_workflow
pushd "${RND_WORKFLOW_SOURCE}" || exit 1
run_ok "${TEST_NAME}" cylc install --run-name=olaf
contains_ok "${TEST_NAME}.stdout" <<__OUT__
INSTALLED ${RND_WORKFLOW_NAME}/olaf from ${RND_WORKFLOW_SOURCE}
__OUT__
TEST_NAME="${TEST_NAME_BASE}-install-twice-same-run-name-2nd-install"
run_fail "${TEST_NAME}" cylc install --run-name=olaf
contains_ok "${TEST_NAME}.stderr" <<__ERR__
WorkflowFilesError: "${RND_WORKFLOW_RUNDIR}/olaf" exists. \
Try using cylc reinstall. Alternatively, install with another name, using the --run-name option.
__ERR__
popd || exit 1
purge_rnd_workflow

# -----------------------------------------------------------------------------
# Test cylc install fails if installation would result in nested run dirs

TEST_NAME="${TEST_NAME_BASE}-nested-rundir"
make_rnd_workflow
mkdir -p "${RND_WORKFLOW_RUNDIR}/.service"
run_fail "${TEST_NAME}-install" cylc install -C "${RND_WORKFLOW_SOURCE}" --flow-name="${RND_WORKFLOW_NAME}/nested"
cmp_ok "${TEST_NAME}-install.stderr" <<__ERR__
WorkflowFilesError: Nested run directories not allowed - cannot install workflow name "${RND_WORKFLOW_NAME}/nested" as "${RND_WORKFLOW_RUNDIR}" is already a valid run directory.
__ERR__
purge_rnd_workflow

# -----------------------------------------------------------------------------
# Test cylc install can not be run from within the cylc-run directory

TEST_NAME="${TEST_NAME_BASE}-forbid-cylc-run-dir-install"
BASE_NAME="test-install-${CYLC_TEST_TIME_INIT}"
mkdir -p "${RUN_DIR}/${BASE_NAME}/${TEST_SOURCE_DIR_BASE}/${TEST_NAME}" && cd "$_" || exit
touch flow.cylc
run_fail "${TEST_NAME}" cylc install
contains_ok "${TEST_NAME}.stderr" <<__ERR__
WorkflowFilesError: ${TEST_NAME} installation failed. Source directory should not be in ${RUN_DIR}
__ERR__

cd "${RUN_DIR}" || exit
rm -rf "${BASE_NAME}"
purge_rnd_workflow

exit
