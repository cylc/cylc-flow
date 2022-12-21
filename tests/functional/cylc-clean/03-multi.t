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
# -----------------------------------------------------------------------------
# Test cleaning multiple run dirs

. "$(dirname "$0")/test_header"
if ! command -v 'tree' > /dev/null; then
    skip_all '"tree" command not available'
fi
set_test_number 18

FUNCTIONAL_DIR="${TEST_SOURCE_DIR_BASE%/*}"

# -----------------------------------------------------------------------------

for _ in 1 2; do
    install_workflow "$TEST_NAME_BASE" basic-workflow true
done

TEST_NAME="tree-pre-clean-1"
run_ok "${TEST_NAME}" tree --noreport --charset=ascii -L 2 \
    "${HOME}/cylc-run/${CYLC_TEST_REG_BASE}/${FUNCTIONAL_DIR}/cylc-clean"
# Note: backticks need to be escaped in the heredoc
cmp_ok "${TEST_NAME}.stdout" << __TREE__
${HOME}/cylc-run/${CYLC_TEST_REG_BASE}/${FUNCTIONAL_DIR}/cylc-clean
\`-- ${TEST_NAME_BASE}
    |-- _cylc-install
    |-- run1
    |-- run2
    \`-- runN -> run2
__TREE__

# Test trying to clean multiple run dirs without --yes fails:
run_fail "${TEST_NAME_BASE}-no" cylc clean "$WORKFLOW_NAME"
exists_ok "${WORKFLOW_RUN_DIR}/run1"
exists_ok "${WORKFLOW_RUN_DIR}/run2"

# Should work with --yes (removes top level dir too):
run_ok "${TEST_NAME_BASE}-yes" cylc clean -y "$WORKFLOW_NAME"
exists_fail "${HOME}/cylc-run/${CYLC_TEST_REG_BASE}"

# -----------------------------------------------------------------------------
# Should continue cleaning a list of workflows even if one fails.

for _ in 1 2; do
    install_workflow "$TEST_NAME_BASE" basic-workflow true
done

TEST_NAME="tree-pre-clean-2"
run_ok "${TEST_NAME}" tree --noreport --charset=ascii -L 2 \
    "${HOME}/cylc-run/${CYLC_TEST_REG_BASE}/${FUNCTIONAL_DIR}/cylc-clean"
cmp_ok "${TEST_NAME}.stdout" << __TREE__
${HOME}/cylc-run/${CYLC_TEST_REG_BASE}/${FUNCTIONAL_DIR}/cylc-clean
\`-- ${TEST_NAME_BASE}
    |-- _cylc-install
    |-- run1
    |-- run2
    \`-- runN -> run2
__TREE__

mkdir "${WORKFLOW_RUN_DIR}/run1/.service"
echo 'x' > "${WORKFLOW_RUN_DIR}/run1/.service/db"  # corrupted db!

TEST_NAME="${TEST_NAME_BASE}-yes-no"
run_fail "${TEST_NAME}" \
    cylc clean -y "$WORKFLOW_NAME/run1" "$WORKFLOW_NAME/run2"

grep_ok "file is not a database" "${TEST_NAME}.stderr" -e

TEST_NAME="tree-post-clean-2"
run_ok "${TEST_NAME}" tree --noreport --charset=ascii -L 2 \
    "${HOME}/cylc-run/${CYLC_TEST_REG_BASE}/${FUNCTIONAL_DIR}/cylc-clean"
cmp_ok "${TEST_NAME}.stdout" << __TREE__
${HOME}/cylc-run/${CYLC_TEST_REG_BASE}/${FUNCTIONAL_DIR}/cylc-clean
\`-- ${TEST_NAME_BASE}
    |-- _cylc-install
    \`-- run1
__TREE__

purge

# -----------------------------------------------------------------------------
# Should not clean top level dir if not empty.

install_workflow "$TEST_NAME_BASE" basic-workflow true

touch "${WORKFLOW_RUN_DIR}/jellyfish.txt"

TEST_NAME="tree-pre-clean-3"
run_ok "${TEST_NAME}" tree --noreport --charset=ascii -L 2 \
    "${HOME}/cylc-run/${CYLC_TEST_REG_BASE}/${FUNCTIONAL_DIR}/cylc-clean"
cmp_ok "${TEST_NAME}.stdout" << __TREE__
${HOME}/cylc-run/${CYLC_TEST_REG_BASE}/${FUNCTIONAL_DIR}/cylc-clean
\`-- ${TEST_NAME_BASE}
    |-- _cylc-install
    |-- jellyfish.txt
    |-- run1
    \`-- runN -> run1
__TREE__

run_ok "${TEST_NAME}" cylc clean -y "$WORKFLOW_NAME"

TEST_NAME="tree-post-clean-3"
run_ok "${TEST_NAME}" tree --noreport --charset=ascii -L 2 \
    "${HOME}/cylc-run/${CYLC_TEST_REG_BASE}/${FUNCTIONAL_DIR}/cylc-clean"
cmp_ok "${TEST_NAME}.stdout" << __TREE__
${HOME}/cylc-run/${CYLC_TEST_REG_BASE}/${FUNCTIONAL_DIR}/cylc-clean
\`-- ${TEST_NAME_BASE}
    |-- _cylc-install
    \`-- jellyfish.txt
__TREE__

purge
