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
set_test_number 45

create_test_global_config '' '
[install]
    max depth = 6
'

# Test source directory between runs that are not consistent result in error

TEST_NAME="${TEST_NAME_BASE}-forbid-inconsistent-source-dir-between-runs"
SOURCE_DIR_1="test-install-${CYLC_TEST_TIME_INIT}/${TEST_NAME_BASE}"
WORKFLOW_NAME="cylctb-${CYLC_TEST_TIME_INIT}/${TEST_SOURCE_DIR##*tests/}/${TEST_NAME}"
mkdir -p "${PWD}/${SOURCE_DIR_1}"
pushd "${SOURCE_DIR_1}" || exit 1
touch flow.cylc
run_ok "${TEST_NAME}" cylc install --workflow-name "$WORKFLOW_NAME"
popd || exit 1

SOURCE_DIR_2="test-install-${CYLC_TEST_TIME_INIT}2/${TEST_NAME_BASE}"
WORKFLOW_NAME="cylctb-${CYLC_TEST_TIME_INIT}/${TEST_SOURCE_DIR##*tests/}/${TEST_NAME}"
mkdir -p "${PWD}/${SOURCE_DIR_2}"
pushd "${SOURCE_DIR_2}" || exit 1
touch flow.cylc
run_fail "${TEST_NAME}" cylc install --workflow-name "$WORKFLOW_NAME"
grep_ok "previous installations were from" "${TEST_NAME}.stderr"
rm -rf "${PWD:?}/${SOURCE_DIR_1}" "${PWD:?}/${SOURCE_DIR_2}"
purge
popd || exit

# -----------------------------------------------------------------------------
# Test fail no flow.cylc or suite.rc file

make_rnd_workflow

TEST_NAME="${TEST_NAME_BASE}-no-flow-file"
rm -f "${RND_WORKFLOW_SOURCE}/flow.cylc"
run_fail "${TEST_NAME}" cylc install --workflow-name="${RND_WORKFLOW_NAME}" "${RND_WORKFLOW_SOURCE}"
contains_ok "${TEST_NAME}.stderr" <<__ERR__
WorkflowFilesError: No flow.cylc or suite.rc in ${RND_WORKFLOW_SOURCE}
__ERR__

# -----------------------------------------------------------------------------
# Test fail both flow.cylc and suite.rc file

make_rnd_workflow

TEST_NAME="${TEST_NAME_BASE}-both-suite-and-flow-file"
touch "${RND_WORKFLOW_SOURCE}/suite.rc"
run_fail "${TEST_NAME}" cylc install --workflow-name="${RND_WORKFLOW_NAME}" "${RND_WORKFLOW_SOURCE}"
contains_ok "${TEST_NAME}.stderr" <<__ERR__
WorkflowFilesError: Both flow.cylc and suite.rc files are present in ${RND_WORKFLOW_SOURCE}. \
Please remove one and try again. For more information visit: \
https://cylc.github.io/cylc-doc/stable/html/7-to-8/summary.html#backward-compatibility
__ERR__

# Test fail no workflow source dir

TEST_NAME="${TEST_NAME_BASE}-nodir"
rm -rf "${RND_WORKFLOW_SOURCE}"
run_fail "${TEST_NAME}" cylc install --workflow-name="${RND_WORKFLOW_NAME}" --no-run-name "${RND_WORKFLOW_SOURCE}"
contains_ok "${TEST_NAME}.stderr" <<__ERR__
WorkflowFilesError: No flow.cylc or suite.rc in ${RND_WORKFLOW_SOURCE}
__ERR__

purge_rnd_workflow

# -----------------------------------------------------------------------------
# Test cylc install fails when given flow-name that is an absolute path

make_rnd_workflow

TEST_NAME="${TEST_NAME_BASE}-no-abs-path-flow-name"
run_fail "${TEST_NAME}" cylc install --workflow-name="${RND_WORKFLOW_SOURCE}" "${RND_WORKFLOW_SOURCE}"
contains_ok "${TEST_NAME}.stderr" <<__ERR__
WorkflowFilesError: workflow name cannot be an absolute path: ${RND_WORKFLOW_SOURCE}
__ERR__

# Test cylc install fails when given forbidden run-name

TEST_NAME="${TEST_NAME_BASE}-run-name-forbidden"
run_fail "${TEST_NAME}" cylc install --run-name=_cylc-install "${RND_WORKFLOW_SOURCE}"
cmp_ok "${TEST_NAME}.stderr" <<__ERR__
WorkflowFilesError: Workflow/run name cannot contain a directory named '_cylc-install' (that filename is reserved)
__ERR__

# Test cylc install invalid flow-name

TEST_NAME="${TEST_NAME_BASE}-invalid-flow-name"
run_fail "${TEST_NAME}" cylc install --workflow-name=".invalid" "${RND_WORKFLOW_SOURCE}"
contains_ok "${TEST_NAME}.stderr" <<__ERR__
WorkflowFilesError: invalid workflow name '.invalid' - cannot start with: \`.\`, \`-\`, numbers
__ERR__

# Test --run-name and --no-run-name options are mutually exclusive

TEST_NAME="${TEST_NAME_BASE}--no-run-name-and--run-name-forbidden"
pushd "${RND_WORKFLOW_SOURCE}" || exit 1
run_fail "${TEST_NAME}" cylc install --run-name="${RND_WORKFLOW_NAME}" --no-run-name
cmp_ok "${TEST_NAME}.stderr" <<__ERR__
InputError: options --no-run-name and --run-name are mutually exclusive.
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
WorkflowFilesError: ${RND_WORKFLOW_NAME} installation failed - ${DIR} exists in source directory.
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
WorkflowFilesError: Path: "${RND_WORKFLOW_RUNDIR}" contains an installed workflow. Use --run-name to create a new run.
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
WorkflowFilesError: --run-name option not allowed as '${RND_WORKFLOW_RUNDIR}' contains installed numbered runs.
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
WorkflowFilesError: '${RND_WORKFLOW_RUNDIR}/olaf' already exists
__ERR__
popd || exit 1
purge_rnd_workflow

# -----------------------------------------------------------------------------
# Test cylc install fails if installation would result in nested run dirs

TEST_NAME="${TEST_NAME_BASE}-nested-rundir"
make_rnd_workflow
mkdir -p "${RND_WORKFLOW_RUNDIR}/.service"
run_fail "${TEST_NAME}-install" cylc install "${RND_WORKFLOW_SOURCE}" \
    --workflow-name="${RND_WORKFLOW_NAME}/nested"
cmp_ok "${TEST_NAME}-install.stderr" <<__ERR__
WorkflowFilesError: Nested run directories not allowed - cannot install workflow in '${RND_WORKFLOW_RUNDIR}/nested/run1' as '${RND_WORKFLOW_RUNDIR}' is already a valid run directory.
__ERR__

# Test moving source dir results in error

TEST_NAME="${TEST_NAME_BASE}-install-moving-src-dir"
make_rnd_workflow
run_ok "${TEST_NAME}" cylc install "./${RND_WORKFLOW_NAME}"
contains_ok "${TEST_NAME}.stdout" <<__OUT__
INSTALLED $RND_WORKFLOW_NAME/run1 from ${PWD}/${RND_WORKFLOW_NAME}
__OUT__
rm -rf "${RND_WORKFLOW_SOURCE}"
ALT_SOURCE="${TMPDIR}/${USER}/cylctb-x$(< /dev/urandom tr -dc _A-Z-a-z-0-9 | head -c6)"
mkdir -p "${ALT_SOURCE}/${RND_WORKFLOW_NAME}"
touch "${ALT_SOURCE}/${RND_WORKFLOW_NAME}/flow.cylc"


TEST_NAME="${TEST_NAME_BASE}-install-twice-moving-src-dir-raises-error"
run_fail "${TEST_NAME}" cylc install "${ALT_SOURCE}/${RND_WORKFLOW_NAME}"
grep_ok "WorkflowFilesError: Symlink broken" "${TEST_NAME}.stderr"

rm -rf "${ALT_SOURCE}"
purge_rnd_workflow

# -----------------------------------------------------------------------------
# --run-name cannot be a path

make_rnd_workflow
TEST_NAME="${TEST_NAME_BASE}-forbid-cylc-run-dir-install"
BASE_NAME="test-install-${CYLC_TEST_TIME_INIT}"
mkdir -p "${RUN_DIR}/${BASE_NAME}/${TEST_SOURCE_DIR_BASE}/${TEST_NAME}" && cd "$_" || exit
touch flow.cylc
run_fail "${TEST_NAME}" cylc install --run-name=foo/bar/baz --workflow-name "$RND_WORKFLOW_NAME"
contains_ok "${TEST_NAME}.stderr" <<__ERR__
WorkflowFilesError: Run name cannot be a path. (You used foo/bar/baz)
__ERR__

cd "${RUN_DIR}" || exit
rm -rf "${BASE_NAME}"
purge_rnd_workflow

exit
