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
# Test workflow installation
. "$(dirname "$0")/test_header"
set_test_number 25

create_test_global_config "" "
[install]
    source dirs = ${PWD}/cylc-src
"
mkdir "cylc-src"

# -----------------------------------------------------------------------------
# Test default name: "cylc install" (flow in $PWD, no args)
TEST_NAME="${TEST_NAME_BASE}-basic"
make_rnd_workflow
pushd "${RND_WORKFLOW_SOURCE}" || exit 1
run_ok "${TEST_NAME}" cylc install

contains_ok "${TEST_NAME}.stdout" <<__OUT__
INSTALLED $RND_WORKFLOW_NAME/run1 from ${RND_WORKFLOW_SOURCE}
__OUT__
popd || exit 1
purge_rnd_workflow

# -----------------------------------------------------------------------------
# Test default name: "cylc install WORKFLOW_NAME" (flow in confgured source dir)
make_rnd_workflow
# Before adding workflow to ~/cylc-src/, check install fails:
TEST_NAME="${TEST_NAME_BASE}-WORKFLOW_NAME-fail-no-src-dir"
run_fail "${TEST_NAME}" cylc install "${RND_WORKFLOW_NAME}"
# Now add workflow to ~/cylc-src/
RND_WORKFLOW_SOURCE="${PWD}/cylc-src/${RND_WORKFLOW_NAME}"
mv "$RND_WORKFLOW_NAME" "${PWD}/cylc-src/"
pushd "${RND_WORKFLOW_SOURCE}" || exit 1
# Test WORKFLOW_NAME and --directory are mutually exclusive
TEST_NAME="${TEST_NAME_BASE}-WORKFLOW_NAME-and--directory-forbidden"
run_fail "${TEST_NAME}" cylc install "${RND_WORKFLOW_NAME}" -C "${RND_WORKFLOW_SOURCE}"
contains_ok "${TEST_NAME}.stderr" <<__ERR__
cylc: error: WORKFLOW_NAME and --directory are mutually exclusive.
__ERR__
# Finally test normal case
TEST_NAME="${TEST_NAME_BASE}-WORKFLOW_NAME-install-ok"
run_ok "${TEST_NAME}" cylc install "${RND_WORKFLOW_NAME}"
contains_ok "${TEST_NAME}.stdout" <<__OUT__
INSTALLED $RND_WORKFLOW_NAME/run1 from ${RND_WORKFLOW_SOURCE}
__OUT__
popd || exit 1
purge_rnd_workflow

# -----------------------------------------------------------------------------
# Test cylc install succeeds if suite.rc file in source dir
TEST_NAME="${TEST_NAME_BASE}-suite.rc"
make_rnd_workflow
rm -f "${RND_WORKFLOW_SOURCE}/flow.cylc"
touch "${RND_WORKFLOW_SOURCE}/suite.rc"
run_ok "${TEST_NAME}" cylc install --flow-name="${RND_WORKFLOW_NAME}" -C "${RND_WORKFLOW_SOURCE}"

contains_ok "${TEST_NAME}.stdout" <<__OUT__
INSTALLED $RND_WORKFLOW_NAME/run1 from ${RND_WORKFLOW_SOURCE}
__OUT__
purge_rnd_workflow

# -----------------------------------------------------------------------------
# Test default path: "cylc install" --no-run-name (flow in $PWD)
TEST_NAME="${TEST_NAME_BASE}-pwd-no-run-name"
make_rnd_workflow
pushd "${RND_WORKFLOW_SOURCE}" || exit 1
run_ok "${TEST_NAME}" cylc install --no-run-name
contains_ok "${TEST_NAME}.stdout" <<__OUT__
INSTALLED $RND_WORKFLOW_NAME from ${RND_WORKFLOW_SOURCE}
__OUT__
popd || exit 1
purge_rnd_workflow

# -----------------------------------------------------------------------------
# Test "cylc install" flow-name given (flow in $PWD)
TEST_NAME="${TEST_NAME_BASE}-flow-name"
make_rnd_workflow
pushd "${RND_WORKFLOW_SOURCE}" || exit 1
run_ok "${TEST_NAME}" cylc install --flow-name="${RND_WORKFLOW_NAME}-olaf"
contains_ok "${TEST_NAME}.stdout" <<__OUT__
INSTALLED ${RND_WORKFLOW_NAME}-olaf/run1 from ${RND_WORKFLOW_SOURCE}
__OUT__
popd || exit 1
rm -rf "${RUN_DIR}/${RND_WORKFLOW_NAME}-olaf"
purge_rnd_workflow

# -----------------------------------------------------------------------------
# Test "cylc install" flow-name given, no run name (flow in $PWD)
TEST_NAME="${TEST_NAME_BASE}-flow-name-no-run-name"
make_rnd_workflow
pushd "${RND_WORKFLOW_SOURCE}" || exit 1
run_ok "${TEST_NAME}" cylc install --flow-name="${RND_WORKFLOW_NAME}-olaf" --no-run-name
contains_ok "${TEST_NAME}.stdout" <<__OUT__
INSTALLED ${RND_WORKFLOW_NAME}-olaf from ${RND_WORKFLOW_SOURCE}
__OUT__
popd || exit 1
rm -rf "${RUN_DIR}/${RND_WORKFLOW_NAME}-olaf"
purge_rnd_workflow

# -----------------------------------------------------------------------------
# Test "cylc install" --directory given (flow in --directory)
TEST_NAME="${TEST_NAME_BASE}-option--directory"
make_rnd_workflow
run_ok "${TEST_NAME}" cylc install --flow-name="${RND_WORKFLOW_NAME}" --directory="${RND_WORKFLOW_SOURCE}"
contains_ok "${TEST_NAME}.stdout" <<__OUT__
INSTALLED $RND_WORKFLOW_NAME/run1 from ${RND_WORKFLOW_SOURCE}
__OUT__
purge_rnd_workflow

# -----------------------------------------------------------------------------
# Test running cylc install twice increments run dirs correctly
TEST_NAME="${TEST_NAME_BASE}-install-twice-1"
make_rnd_workflow
pushd "${RND_WORKFLOW_SOURCE}" || exit 1
run_ok "${TEST_NAME}" cylc install
contains_ok "${TEST_NAME}.stdout" <<__OUT__
INSTALLED $RND_WORKFLOW_NAME/run1 from ${RND_WORKFLOW_SOURCE}
__OUT__
TEST_NAME="${TEST_NAME_BASE}-install-twice-2"
run_ok "${TEST_NAME}" cylc install
contains_ok "${TEST_NAME}.stdout" <<__OUT__
INSTALLED $RND_WORKFLOW_NAME/run2 from ${RND_WORKFLOW_SOURCE}
__OUT__
popd || exit 1
purge_rnd_workflow

# -----------------------------------------------------------------------------
# Test running cylc install twice increments run dirs correctly
TEST_NAME="${TEST_NAME_BASE}-install-C-twice-1"
make_rnd_workflow
run_ok "${TEST_NAME}" cylc install -C "${RND_WORKFLOW_NAME}"
contains_ok "${TEST_NAME}.stdout" <<__OUT__
INSTALLED $RND_WORKFLOW_NAME/run1 from ${RND_WORKFLOW_NAME}
__OUT__
TEST_NAME="${TEST_NAME_BASE}-install-C-twice-2"
run_ok "${TEST_NAME}" cylc install -C "${RND_WORKFLOW_NAME}"
contains_ok "${TEST_NAME}.stdout" <<__OUT__
INSTALLED $RND_WORKFLOW_NAME/run2 from ${RND_WORKFLOW_NAME}
__OUT__
purge_rnd_workflow


exit
