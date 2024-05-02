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
# Test cylc show for a basic task.
. "$(dirname "$0")/test_header"

#-------------------------------------------------------------------------------
set_test_number 8
#-------------------------------------------------------------------------------
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
#-------------------------------------------------------------------------------
TEST_SHOW_OUTPUT_PATH="${PWD}/${TEST_NAME_BASE}-show"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate \
    --set="TEST_OUTPUT_PATH='${TEST_SHOW_OUTPUT_PATH}'" "${WORKFLOW_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-run"
workflow_run_ok "${TEST_NAME}" cylc play --reference-test --debug --no-detach \
    --set="TEST_OUTPUT_PATH='${TEST_SHOW_OUTPUT_PATH}'" "${WORKFLOW_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-show"
cmp_ok "${TEST_NAME}-workflow" <<'__SHOW_OUTPUT__'
title: a test workflow
description: the quick brown fox
custom: custard
URL: (not given)
__SHOW_OUTPUT__

cmp_ok "${TEST_NAME}-task" <<'__SHOW_OUTPUT__'
title: a task
description: jumped over the lazy dog
baz: pub
URL: (not given)
__SHOW_OUTPUT__

cmp_ok "${TEST_NAME}-taskinstance" <<'__SHOW_OUTPUT__'
title: a task
description: jumped over the lazy dog
baz: pub
URL: (not given)
state: running
prerequisites: ('⨯': not satisfied)
  ✓ 20141106T0900Z/bar succeeded
outputs: ('⨯': not completed)
  ⨯ 20141106T0900Z/foo expired
  ✓ 20141106T0900Z/foo submitted
  ⨯ 20141106T0900Z/foo submit-failed
  ✓ 20141106T0900Z/foo started
  ⨯ 20141106T0900Z/foo succeeded
  ⨯ 20141106T0900Z/foo failed
output completion: incomplete
    ⦙  (
  ✓ ⦙    started
  ⨯ ⦙    and succeeded
    ⦙  )
__SHOW_OUTPUT__
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-show-json"
cmp_json "${TEST_NAME}-workflow" "${TEST_NAME}-workflow" <<'__SHOW_OUTPUT__'
{
    "title": "a test workflow",
    "description": "the quick brown fox",
    "URL": "",
    "custom": "custard"
}
__SHOW_OUTPUT__

cmp_json "${TEST_NAME}-task" "${TEST_NAME}-task" <<'__SHOW_OUTPUT__'
{
    "foo": {
        "title": "a task",
        "description": "jumped over the lazy dog",
        "URL": "",
        "baz": "pub"
    }
}
__SHOW_OUTPUT__

cmp_json "${TEST_NAME}-taskinstance" "${TEST_NAME}-taskinstance" \
    <<__SHOW_OUTPUT__
{
    "20141106T0900Z/foo": {
        "name": "foo",
        "id": "~${USER}/${WORKFLOW_NAME}//20141106T0900Z/foo",
        "cyclePoint": "20141106T0900Z",
        "state": "running",
        "task": {
            "meta": {
                "title": "a task",
                "description": "jumped over the lazy dog",
                "URL": "",
                "userDefined": {
                    "baz": "pub"
                }
            }
        },
        "runtime": {"completion": "(started and succeeded)"},
        "prerequisites": [
            {
                "expression": "c0",
                "conditions": [
                    {
                        "exprAlias": "c0",
                        "taskId": "20141106T0900Z/bar",
                        "reqState": "succeeded",
                        "message": "satisfied naturally",
                        "satisfied": true
                    }
                ],
                "satisfied": true
            }
        ],
        "outputs": [
            {"label": "expired", "message": "expired", "satisfied": false},
            {"label": "submitted", "message": "submitted", "satisfied": true},
            {"label": "submit-failed", "message": "submit-failed", "satisfied": false},
            {"label": "started", "message": "started", "satisfied": true},
            {"label": "succeeded", "message": "succeeded", "satisfied": false},
            {"label": "failed", "message": "failed", "satisfied": false}
        ],
        "externalTriggers": [],
        "xtriggers": []
    }
}
__SHOW_OUTPUT__
#-------------------------------------------------------------------------------
purge
exit
