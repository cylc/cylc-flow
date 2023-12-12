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
# Test that cylc clean succesfully removes the workflow on remote host

export REQUIRE_PLATFORM='loc:remote fs:indep'
. "$(dirname "$0")/test_header"

SSH_CMD="$(cylc config -d -i "[platforms][${CYLC_TEST_PLATFORM}]ssh command") ${CYLC_TEST_HOST}"

if ! $SSH_CMD command -v 'tree' > '/dev/null'; then
    skip_all "'tree' command not available on remote host ${CYLC_TEST_HOST}"
fi
set_test_number 10

# Generate random name for symlink dirs to avoid any clashes with other tests
SYM_NAME="$(mktemp -u)"
SYM_NAME="${SYM_NAME##*tmp.}"

create_test_global_config "" "
[install]
    [[symlink dirs]]
        [[[${CYLC_TEST_INSTALL_TARGET}]]]
            run = ${TEST_DIR}/${SYM_NAME}/run
            log = ${TEST_DIR}/${SYM_NAME}/other
            share = ${TEST_DIR}/${SYM_NAME}/other
            share/cycle = ${TEST_DIR}/${SYM_NAME}/cycle
            work = ${TEST_DIR}/${SYM_NAME}/other
"
init_workflow "${TEST_NAME_BASE}" << __FLOW__
[scheduler]
    allow implicit tasks = True
[scheduling]
    [[graph]]
        R1 = santa
[runtime]
    [[root]]
        platform = ${CYLC_TEST_PLATFORM}
        script = touch flow.cylc # testing that remote clean does not scan for workflows
__FLOW__

FUNCTIONAL_DIR="${TEST_SOURCE_DIR_BASE%/*}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "$WORKFLOW_NAME"

workflow_run_ok "${TEST_NAME_BASE}-run" cylc play "$WORKFLOW_NAME" --no-detach

# Create a fake sibling workflow dir:
$SSH_CMD mkdir "${TEST_DIR}/${SYM_NAME}/cycle/cylc-run/${CYLC_TEST_REG_BASE}/leave-me-alone"

# -----------------------------------------------------------------------------

TEST_NAME="run-dir-readlink-pre-clean.remote"
$SSH_CMD readlink "\$HOME/cylc-run/${WORKFLOW_NAME}" > "${TEST_NAME}.stdout"
cmp_ok "${TEST_NAME}.stdout" <<< "${TEST_DIR}/${SYM_NAME}/run/cylc-run/${WORKFLOW_NAME}"

TEST_NAME="test-dir-tree-pre-clean.remote"
# shellcheck disable=SC2086
run_ok "${TEST_NAME}" $SSH_CMD tree -L 8 --noreport --charset=ascii \
    "${TEST_DIR}/${SYM_NAME}/"'*'"/cylc-run/${CYLC_TEST_REG_BASE}"
# Note: backticks need to be escaped in the heredoc
cmp_ok "${TEST_NAME}.stdout" << __TREE__
${TEST_DIR}/${SYM_NAME}/cycle/cylc-run/${CYLC_TEST_REG_BASE}
|-- ${FUNCTIONAL_DIR}
|   \`-- cylc-clean
|       \`-- ${TEST_NAME_BASE}
|           \`-- share
|               \`-- cycle
\`-- leave-me-alone
${TEST_DIR}/${SYM_NAME}/other/cylc-run/${CYLC_TEST_REG_BASE}
\`-- ${FUNCTIONAL_DIR}
    \`-- cylc-clean
        \`-- ${TEST_NAME_BASE}
            |-- log
            |   \`-- job
            |       \`-- 1
            |           \`-- santa
            |               |-- 01
            |               \`-- NN -> 01
            |-- share
            |   \`-- cycle -> ${TEST_DIR}/${SYM_NAME}/cycle/cylc-run/${WORKFLOW_NAME}/share/cycle
            \`-- work
                \`-- 1
                    \`-- santa
                        \`-- flow.cylc
${TEST_DIR}/${SYM_NAME}/run/cylc-run/${CYLC_TEST_REG_BASE}
\`-- ${FUNCTIONAL_DIR}
    \`-- cylc-clean
        \`-- ${TEST_NAME_BASE}
            |-- log -> ${TEST_DIR}/${SYM_NAME}/other/cylc-run/${WORKFLOW_NAME}/log
            |-- share -> ${TEST_DIR}/${SYM_NAME}/other/cylc-run/${WORKFLOW_NAME}/share
            \`-- work -> ${TEST_DIR}/${SYM_NAME}/other/cylc-run/${WORKFLOW_NAME}/work
__TREE__

# -----------------------------------------------------------------------------

TEST_NAME="cylc-clean-ok"
run_ok "$TEST_NAME" cylc clean "$WORKFLOW_NAME" --timeout PT2M
# (timeout opt is covered by unit tests but no harm double-checking here)
dump_std "$TEST_NAME"

TEST_NAME="run-dir-not-exist-post-clean.local"
# (Could use the function `exists_ok` here instead, but this keeps it consistent with the remote test below)
if [[ ! -a "$WORKFLOW_RUN_DIR" ]]; then
    ok "$TEST_NAME"
else
    fail "$TEST_NAME"
fi

TEST_NAME="run-dir-not-exist-post-clean.remote"
if $SSH_CMD [[ ! -a "\$HOME/cylc-run/${WORKFLOW_NAME}" ]]; then
    ok "$TEST_NAME"
else
    fail "$TEST_NAME"
fi

TEST_NAME="test-dir-tree-post-clean.remote"
# shellcheck disable=SC2086
run_ok "${TEST_NAME}" $SSH_CMD tree --noreport --charset=ascii \
    "${TEST_DIR}/${SYM_NAME}/"'*'"/cylc-run/${CYLC_TEST_REG_BASE}"
# Note: backticks need to be escaped in the heredoc
cmp_ok "${TEST_NAME}.stdout" << __TREE__
${TEST_DIR}/${SYM_NAME}/cycle/cylc-run/${CYLC_TEST_REG_BASE}
\`-- leave-me-alone
__TREE__

purge
