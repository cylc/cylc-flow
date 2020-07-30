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
#-------------------------------------------------------------------------------
# Test cylc show for a basic task.
. "$(dirname "$0")/test_header"

#-------------------------------------------------------------------------------
set_test_number 8
#-------------------------------------------------------------------------------
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
#-------------------------------------------------------------------------------
TEST_SHOW_OUTPUT_PATH="${PWD}/${TEST_NAME_BASE}-show"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate \
    --set=TEST_OUTPUT_PATH="${TEST_SHOW_OUTPUT_PATH}" "${SUITE_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-run"
suite_run_ok "${TEST_NAME}" cylc run --reference-test --debug --no-detach \
    --set=TEST_OUTPUT_PATH="${TEST_SHOW_OUTPUT_PATH}" "${SUITE_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-show"
cmp_ok "${TEST_NAME}-suite" <<'__SHOW_OUTPUT__'
title: a test suite
group: (not given)
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

prerequisites (- => not satisfied):
  + bar.20141106T0900Z succeeded

outputs (- => not completed):
  - foo.20141106T0900Z expired
  + foo.20141106T0900Z submitted
  - foo.20141106T0900Z submit-failed
  + foo.20141106T0900Z started
  - foo.20141106T0900Z succeeded
  - foo.20141106T0900Z failed
__SHOW_OUTPUT__
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-show-json"
cmp_json "${TEST_NAME}-suite" "${TEST_NAME}-suite" <<'__SHOW_OUTPUT__'
[
    {
        "URL": "", 
        "custom": "custard", 
        "group": "", 
        "description": "the quick brown fox", 
        "title": "a test suite"
    }
]
__SHOW_OUTPUT__

cmp_json "${TEST_NAME}-task" "${TEST_NAME}-task" <<'__SHOW_OUTPUT__'
[
    {
        "foo": {
            "URL": "", 
            "baz": "pub", 
            "description": "jumped over the lazy dog", 
            "title": "a task"
        }
    }
]
__SHOW_OUTPUT__

cmp_json "${TEST_NAME}-taskinstance" "${TEST_NAME}-taskinstance" \
    <<'__SHOW_OUTPUT__'
[
    {
        "foo.20141106T0900Z": {
            "prerequisites": [
                [
                    "bar.20141106T0900Z succeeded", 
                    "satisfied naturally"
                ]
            ], 
            "outputs": [
                [
                    "foo.20141106T0900Z expired", 
                    false
                ], 
                [
                    "foo.20141106T0900Z submitted", 
                    true
                ], 
                [
                    "foo.20141106T0900Z submit-failed", 
                    false
                ], 
                [
                    "foo.20141106T0900Z started", 
                    true
                ], 
                [
                    "foo.20141106T0900Z succeeded", 
                    false
                ],
                [
                    "foo.20141106T0900Z failed", 
                    false
                ]
            ], 
            "meta": {
                "URL": "", 
                "baz": "pub", 
                "description": "jumped over the lazy dog", 
                "title": "a task"
            }, 
            "extras": {}
        }
    }
]
__SHOW_OUTPUT__
#-------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"
exit
