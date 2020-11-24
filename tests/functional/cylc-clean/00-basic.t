#!/bin/bash
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
set_test_number 5

create_test_global_config "" "
[symlink dirs]
    [[localhost]]
        run = ${TEST_DIR}/sym-run
        log = ${TEST_DIR}/sym-log
        share = ${TEST_DIR}/sym-share
        share/cycle = ${TEST_DIR}/sym-cycle
        work = ${TEST_DIR}/sym-work
"
init_suite "${TEST_NAME_BASE}" << '__FLOW__'
[scheduling]
    [[graph]]
        R1 = darmok
__FLOW__
# -----------------------------------------------------------------------------
TEST_NAME="run-dir-tree-pre-clean"
tree "$SUITE_RUN_DIR" > "${TEST_NAME}.stdout"
# Remove last line of output:
sed -i '$d' "${TEST_NAME}.stdout"

cmp_ok "${TEST_NAME}.stdout" << __TREE__
${HOME}/cylc-run/${SUITE_NAME}
|-- log -> ${TEST_DIR}/sym-log/cylc-run/${SUITE_NAME}/log
|-- share -> ${TEST_DIR}/sym-share/cylc-run/${SUITE_NAME}/share
\`-- work -> ${TEST_DIR}/sym-work/cylc-run/${SUITE_NAME}/work

__TREE__

TEST_NAME="test-dir-tree-pre-clean"
tree "${TEST_DIR}/sym-"* > "${TEST_NAME}.stdout"
# Remove last line of output:
sed -i '$d' "${TEST_NAME}.stdout"
# Note: backticks need to be escaped in the heredoc
cmp_ok "${TEST_NAME}.stdout" << __TREE__
${TEST_DIR}/sym-cycle
\`-- cylc-run
    \`-- cylctb-${CYLC_TEST_TIME_INIT}
        \`-- f
            \`-- cylc-clean
                \`-- ${TEST_NAME_BASE}
                    \`-- share
                        \`-- cycle
${TEST_DIR}/sym-log
\`-- cylc-run
    \`-- cylctb-${CYLC_TEST_TIME_INIT}
        \`-- f
            \`-- cylc-clean
                \`-- ${TEST_NAME_BASE}
                    \`-- log
${TEST_DIR}/sym-run
\`-- cylc-run
    \`-- cylctb-${CYLC_TEST_TIME_INIT}
        \`-- f
            \`-- cylc-clean
                \`-- ${TEST_NAME_BASE}
                    |-- log -> ${TEST_DIR}/sym-log/cylc-run/${SUITE_NAME}/log
                    |-- share -> ${TEST_DIR}/sym-share/cylc-run/${SUITE_NAME}/share
                    \`-- work -> ${TEST_DIR}/sym-work/cylc-run/${SUITE_NAME}/work
${TEST_DIR}/sym-share
\`-- cylc-run
    \`-- cylctb-${CYLC_TEST_TIME_INIT}
        \`-- f
            \`-- cylc-clean
                \`-- ${TEST_NAME_BASE}
                    \`-- share
                        \`-- cycle -> ${TEST_DIR}/sym-cycle/cylc-run/${SUITE_NAME}/share/cycle
${TEST_DIR}/sym-work
\`-- cylc-run
    \`-- cylctb-${CYLC_TEST_TIME_INIT}
        \`-- f
            \`-- cylc-clean
                \`-- ${TEST_NAME_BASE}
                    \`-- work

__TREE__
# -----------------------------------------------------------------------------
run_ok "cylc-clean" cylc clean "$SUITE_NAME"
# -----------------------------------------------------------------------------
TEST_NAME="run-dir-not-exist-post-clean"
exists_fail "$SUITE_RUN_DIR"

TEST_NAME="test-dir-tree-post-clean"
tree "${TEST_DIR}/sym-"* > "${TEST_NAME}.stdout"
# Remove last line of output:
sed -i '$d' "${TEST_NAME}.stdout"

cmp_ok "${TEST_NAME}.stdout" << __TREE__
${TEST_DIR}/sym-cycle
\`-- cylc-run
${TEST_DIR}/sym-log
\`-- cylc-run
${TEST_DIR}/sym-run
\`-- cylc-run
${TEST_DIR}/sym-share
\`-- cylc-run
${TEST_DIR}/sym-work
\`-- cylc-run

__TREE__
# -----------------------------------------------------------------------------
purge
exit
