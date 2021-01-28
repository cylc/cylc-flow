#!/usr/bin/env bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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
set_test_number 8

# Generate randome name for symlink firs to avoid any clashed with other tests
SYM_NAME="$(mktemp -u)"
SYM_NAME="${SYM_NAME##*tmp.}"

create_test_global_config "" "
[symlink dirs]
    [[localhost]]
        run = ${TEST_DIR}/${SYM_NAME}/run
        log = ${TEST_DIR}/${SYM_NAME}/log
        share = ${TEST_DIR}/${SYM_NAME}/share
        share/cycle = ${TEST_DIR}/${SYM_NAME}/cycle
        work = ${TEST_DIR}/${SYM_NAME}/work
"
init_suite "${TEST_NAME_BASE}" << '__FLOW__'
[scheduling]
    [[graph]]
        R1 = darmok
__FLOW__

run_ok "${TEST_NAME_BASE}-val" cylc validate "$SUITE_NAME"

# Create a fake sibling workflow dir in the ${SYM_NAME}/log dir:
mkdir "${TEST_DIR}/${SYM_NAME}/log/cylc-run/${CYLC_TEST_REG_BASE}/leave-me-alone"

FUNCTIONAL_DIR="${TEST_SOURCE_DIR_BASE%/*}"
# -----------------------------------------------------------------------------
TEST_NAME="run-dir-readlink-pre-clean"
readlink "$SUITE_RUN_DIR" > "${TEST_NAME}.stdout"

cmp_ok "${TEST_NAME}.stdout" <<< "${TEST_DIR}/${SYM_NAME}/run/cylc-run/${SUITE_NAME}"


INSTALL_LOG_FILE=$(ls "${TEST_DIR}/${SYM_NAME}/log/cylc-run/${SUITE_NAME}/log/install")
TEST_NAME="test-dir-tree-pre-clean"
run_ok "${TEST_NAME}" tree --noreport --charset=ascii "${TEST_DIR}/${SYM_NAME}/"*"/cylc-run/${CYLC_TEST_REG_BASE}"
# Note: backticks need to be escaped in the heredoc
cmp_ok "${TEST_NAME}.stdout" << __TREE__
${TEST_DIR}/${SYM_NAME}/cycle/cylc-run/${CYLC_TEST_REG_BASE}
\`-- ${FUNCTIONAL_DIR}
    \`-- cylc-clean
        \`-- ${TEST_NAME_BASE}
            \`-- share
                \`-- cycle
${TEST_DIR}/${SYM_NAME}/log/cylc-run/${CYLC_TEST_REG_BASE}
|-- ${FUNCTIONAL_DIR}
|   \`-- cylc-clean
|       \`-- ${TEST_NAME_BASE}
|           \`-- log
|               \`-- install
|                   \`-- ${INSTALL_LOG_FILE}
\`-- leave-me-alone
${TEST_DIR}/${SYM_NAME}/run/cylc-run/${CYLC_TEST_REG_BASE}
\`-- ${FUNCTIONAL_DIR}
    \`-- cylc-clean
        \`-- ${TEST_NAME_BASE}
            |-- _cylc-install
            |   \`-- source -> ${TEST_DIR}/${SUITE_NAME}
            |-- flow.cylc
            |-- log -> ${TEST_DIR}/${SYM_NAME}/log/cylc-run/${SUITE_NAME}/log
            |-- opt
            |   \`-- rose-suite-cylc-install.conf
            |-- rose-suite.conf
            |-- share -> ${TEST_DIR}/${SYM_NAME}/share/cylc-run/${SUITE_NAME}/share
            \`-- work -> ${TEST_DIR}/${SYM_NAME}/work/cylc-run/${SUITE_NAME}/work
${TEST_DIR}/${SYM_NAME}/share/cylc-run/${CYLC_TEST_REG_BASE}
\`-- ${FUNCTIONAL_DIR}
    \`-- cylc-clean
        \`-- ${TEST_NAME_BASE}
            \`-- share
                \`-- cycle -> ${TEST_DIR}/${SYM_NAME}/cycle/cylc-run/${SUITE_NAME}/share/cycle
${TEST_DIR}/${SYM_NAME}/work/cylc-run/${CYLC_TEST_REG_BASE}
\`-- ${FUNCTIONAL_DIR}
    \`-- cylc-clean
        \`-- ${TEST_NAME_BASE}
            \`-- work
__TREE__
# -----------------------------------------------------------------------------
TEST_NAME="cylc-clean"
run_ok "$TEST_NAME" cylc clean "$SUITE_NAME"
dump_std "$TEST_NAME"
# -----------------------------------------------------------------------------
TEST_NAME="run-dir-not-exist-post-clean"
exists_fail "$SUITE_RUN_DIR"

TEST_NAME="test-dir-tree-post-clean"
run_ok "${TEST_NAME}" tree --noreport --charset=ascii "${TEST_DIR}/${SYM_NAME}/"*"/cylc-run/${CYLC_TEST_REG_BASE}"

cmp_ok "${TEST_NAME}.stdout" << __TREE__
${TEST_DIR}/${SYM_NAME}/log/cylc-run/${CYLC_TEST_REG_BASE}
\`-- leave-me-alone
__TREE__
# -----------------------------------------------------------------------------
purge
exit
