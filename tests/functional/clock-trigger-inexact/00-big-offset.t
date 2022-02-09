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

# Test clock triggers (xtrigger and old-style) with a large inexact offset.

. "$(dirname "$0")/test_header"
skip_all 'TODO: fix test https://github.com/cylc/cylc-flow/issues/4633'
set_test_number 5
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-val" cylc validate "${WORKFLOW_NAME}"
workflow_run_ok "${TEST_NAME_BASE}-run" cylc play --no-detach "${WORKFLOW_NAME}"

cylc cat-log "${WORKFLOW_NAME}" > log 
START_HOUR=$(grep 'Workflow:' log | cut -c 1-13)
START_MINU=$(grep 'Workflow:' log | cut -c 15-16)
TRIGG_MINU=$(( 10#${START_MINU} + 1))
[[ $START_MINU == 0* ]] && TRIGG_MINU=0${TRIGG_MINU}

for NAME in foo bar baz; do
   grep_ok "${START_HOUR}:${TRIGG_MINU}.* INFO - \[.*/${NAME} .*\] => waiting$" log
done

purge
