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
#-------------------------------------------------------------------------------
# Test calling "cylc shutdown workflow1" from workflow2.
# See https://github.com/cylc/cylc-flow/issues/1843
. "$(dirname "$0")/test_header"

set_test_number 1
RUND="$RUN_DIR"
NAME1="${CYLC_TEST_REG_BASE}/${TEST_SOURCE_DIR_BASE}/${TEST_NAME_BASE}-1"
NAME2="${CYLC_TEST_REG_BASE}/${TEST_SOURCE_DIR_BASE}/${TEST_NAME_BASE}-2"
WORKFLOW1_RUND="${RUND}/${NAME1}"
RND_WORKFLOW_NAME=x$(< /dev/urandom tr -dc _A-Z-a-z-0-9 | head -c6)
RND_WORKFLOW_SOURCE="$PWD/${RND_WORKFLOW_NAME}"
mkdir -p "${RND_WORKFLOW_SOURCE}"
cp -p "${TEST_SOURCE_DIR}/basic/flow.cylc" "${RND_WORKFLOW_SOURCE}"
cylc install --workflow-name="${NAME1}" --directory="${RND_WORKFLOW_SOURCE}" --no-run-name

RND_WORKFLOW_NAME2=x$(< /dev/urandom tr -dc _A-Z-a-z-0-9 | head -c6)
RND_WORKFLOW_SOURCE2="$PWD/${RND_WORKFLOW_NAME2}"
mkdir -p "${RND_WORKFLOW_SOURCE2}"
cat >"${RND_WORKFLOW_SOURCE2}/flow.cylc" <<__FLOW_CONFIG__
[scheduler]
    [[events]]
[scheduling]
    [[graph]]
        R1=t1
[runtime]
    [[t1]]
        script=cylc shutdown "${NAME1}"
__FLOW_CONFIG__
cylc install --workflow-name="${NAME2}" --directory="${RND_WORKFLOW_SOURCE2}" --no-run-name
cylc play --no-detach "${NAME1}" 1>'1.out' 2>&1 &
WORKFLOW_RUN_DIR="${WORKFLOW1_RUND}" poll_workflow_running
run_ok "${TEST_NAME_BASE}" cylc play --no-detach --abort-if-any-task-fails "${NAME2}"
cylc shutdown "${NAME1}" --max-polls=20 --interval=1 1>'/dev/null' 2>&1 || true
purge "${NAME1}"
purge "${NAME2}"
rm -rf "${RND_WORKFLOW_SOURCE}"
rm -rf "${RND_WORKFLOW_SOURCE2}"
exit
