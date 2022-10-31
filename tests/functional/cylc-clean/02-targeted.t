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
# Test the cylc clean command

. "$(dirname "$0")/test_header"
if ! command -v 'tree' >'/dev/null'; then
    skip_all '"tree" command not available'
fi
set_test_number 16

# Generate random name for symlink dirs to avoid any clashes with other tests
SYM_NAME="$(mktemp -u)"
SYM_NAME="sym-${SYM_NAME##*tmp.}"

create_test_global_config "" "
[install]
    [[symlink dirs]]
        [[[localhost]]]
            run = ${TEST_DIR}/${SYM_NAME}/run
            log = ${TEST_DIR}/${SYM_NAME}/other
            share = ${TEST_DIR}/${SYM_NAME}/other
            work = ${TEST_DIR}/${SYM_NAME}/other
            # Need to override any symlink dirs set in global.cylc:
            share/cycle =
"
install_workflow "${TEST_NAME_BASE}" basic-workflow
# Also create some other file
touch "${WORKFLOW_RUN_DIR}/darmok.cylc"

run_ok "${TEST_NAME_BASE}-val" cylc validate "$WORKFLOW_NAME"

FUNCTIONAL_DIR="${TEST_SOURCE_DIR_BASE%/*}"
# -----------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-run-dir-readlink-pre-clean"
readlink "$WORKFLOW_RUN_DIR" > "${TEST_NAME}.stdout"
cmp_ok "${TEST_NAME}.stdout" <<< "${TEST_DIR}/${SYM_NAME}/run/cylc-run/${WORKFLOW_NAME}"

TEST_NAME="${TEST_NAME_BASE}-testdir-tree-pre-clean"
run_ok "${TEST_NAME}" tree -L 5 --noreport --charset=ascii "${TEST_DIR}/${SYM_NAME}/"*"/cylc-run/${CYLC_TEST_REG_BASE}"
# Note: backticks need to be escaped in the heredoc
cmp_ok "${TEST_NAME}.stdout" << __TREE__
${TEST_DIR}/${SYM_NAME}/other/cylc-run/${CYLC_TEST_REG_BASE}
\`-- ${FUNCTIONAL_DIR}
    \`-- cylc-clean
        \`-- ${TEST_NAME_BASE}
            |-- log
            |   |-- db
            |   \`-- install
            |-- share
            \`-- work
${TEST_DIR}/${SYM_NAME}/run/cylc-run/${CYLC_TEST_REG_BASE}
\`-- ${FUNCTIONAL_DIR}
    \`-- cylc-clean
        \`-- ${TEST_NAME_BASE}
            |-- _cylc-install
            |   \`-- source -> ${TEST_DIR}/${WORKFLOW_NAME}
            |-- darmok.cylc
            |-- flow.cylc
            |-- log -> ${TEST_DIR}/${SYM_NAME}/other/cylc-run/${WORKFLOW_NAME}/log
            |-- share -> ${TEST_DIR}/${SYM_NAME}/other/cylc-run/${WORKFLOW_NAME}/share
            \`-- work -> ${TEST_DIR}/${SYM_NAME}/other/cylc-run/${WORKFLOW_NAME}/work
__TREE__
# -----------------------------------------------------------------------------
# Clean the log dir only
run_ok "${TEST_NAME_BASE}-targeted-clean-1" cylc clean "$WORKFLOW_NAME" \
    --rm log

TEST_NAME="${TEST_NAME_BASE}-testdir-tree-1"
run_ok "${TEST_NAME}" tree -L 5 --noreport --charset=ascii "${TEST_DIR}/${SYM_NAME}/"*"/cylc-run/${CYLC_TEST_REG_BASE}"
cmp_ok "${TEST_NAME}.stdout" << __TREE__
${TEST_DIR}/${SYM_NAME}/other/cylc-run/${CYLC_TEST_REG_BASE}
\`-- ${FUNCTIONAL_DIR}
    \`-- cylc-clean
        \`-- ${TEST_NAME_BASE}
            |-- share
            \`-- work
${TEST_DIR}/${SYM_NAME}/run/cylc-run/${CYLC_TEST_REG_BASE}
\`-- ${FUNCTIONAL_DIR}
    \`-- cylc-clean
        \`-- ${TEST_NAME_BASE}
            |-- _cylc-install
            |   \`-- source -> ${TEST_DIR}/${WORKFLOW_NAME}
            |-- darmok.cylc
            |-- flow.cylc
            |-- share -> ${TEST_DIR}/${SYM_NAME}/other/cylc-run/${WORKFLOW_NAME}/share
            \`-- work -> ${TEST_DIR}/${SYM_NAME}/other/cylc-run/${WORKFLOW_NAME}/work
__TREE__
# -----------------------------------------------------------------------------
# Clean using a glob
run_ok "${TEST_NAME_BASE}-targeted-clean-2" cylc clean "$WORKFLOW_NAME" \
    --rm 'wo*'

TEST_NAME="${TEST_NAME_BASE}-testdir-tree-2"
run_ok "${TEST_NAME}" tree -L 5 --noreport --charset=ascii "${TEST_DIR}/${SYM_NAME}/"*"/cylc-run/${CYLC_TEST_REG_BASE}"
# Note: when using glob, the symlink dir target is not deleted
cmp_ok "${TEST_NAME}.stdout" << __TREE__
${TEST_DIR}/${SYM_NAME}/other/cylc-run/${CYLC_TEST_REG_BASE}
\`-- ${FUNCTIONAL_DIR}
    \`-- cylc-clean
        \`-- ${TEST_NAME_BASE}
            \`-- share
${TEST_DIR}/${SYM_NAME}/run/cylc-run/${CYLC_TEST_REG_BASE}
\`-- ${FUNCTIONAL_DIR}
    \`-- cylc-clean
        \`-- ${TEST_NAME_BASE}
            |-- _cylc-install
            |   \`-- source -> ${TEST_DIR}/${WORKFLOW_NAME}
            |-- darmok.cylc
            |-- flow.cylc
            \`-- share -> ${TEST_DIR}/${SYM_NAME}/other/cylc-run/${WORKFLOW_NAME}/share
__TREE__
# -----------------------------------------------------------------------------
# Clean the last remaining symlink dir
run_ok "${TEST_NAME_BASE}-targeted-clean-3" cylc clean "$WORKFLOW_NAME" \
    --rm 'share'

TEST_NAME="${TEST_NAME_BASE}-testdir-tree-3"
run_ok "${TEST_NAME}" tree -L 5 --noreport --charset=ascii "${TEST_DIR}/${SYM_NAME}/"*"/cylc-run/${CYLC_TEST_REG_BASE}"
cmp_ok "${TEST_NAME}.stdout" << __TREE__
${TEST_DIR}/${SYM_NAME}/run/cylc-run/${CYLC_TEST_REG_BASE}
\`-- ${FUNCTIONAL_DIR}
    \`-- cylc-clean
        \`-- ${TEST_NAME_BASE}
            |-- _cylc-install
            |   \`-- source -> ${TEST_DIR}/${WORKFLOW_NAME}
            |-- darmok.cylc
            \`-- flow.cylc
__TREE__
# -----------------------------------------------------------------------------
# Clean multiple things
run_ok "${TEST_NAME_BASE}-targeted-clean-3" cylc clean "$WORKFLOW_NAME" \
    --rm 'flow.cylc' --rm 'darmok.cylc'

TEST_NAME="${TEST_NAME_BASE}-testdir-tree-3"
run_ok "${TEST_NAME}" tree -L 5 --noreport --charset=ascii "${TEST_DIR}/${SYM_NAME}/"*"/cylc-run/${CYLC_TEST_REG_BASE}"
cmp_ok "${TEST_NAME}.stdout" << __TREE__
${TEST_DIR}/${SYM_NAME}/run/cylc-run/${CYLC_TEST_REG_BASE}
\`-- ${FUNCTIONAL_DIR}
    \`-- cylc-clean
        \`-- ${TEST_NAME_BASE}
            \`-- _cylc-install
                \`-- source -> ${TEST_DIR}/${WORKFLOW_NAME}
__TREE__
# -----------------------------------------------------------------------------
purge
exit
