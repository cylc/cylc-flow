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
# Test restarting a simple workflow with a task still running (orphaned)
. "$(dirname "$0")/test_header"
set_test_number 3
init_workflow "${TEST_NAME_BASE}" <<'__FLOW_CONFIG__'
#!Jinja2

{{ assert(a_str is string, 'variable "a_str" was not a string') }}
{{ assert(an_int is integer, 'variable "an_int" was not an int') }}
{{ assert(a_float is float, 'variable "a_float" was not a float') }}


[scheduler]
    allow implicit tasks = True
[scheduling]
   [[graph]]
        R1 = foo
__FLOW_CONFIG__


#-------------------------------------------------------------------------------
run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}" \
    --set "a_str='foo'" --set "an_int=24" --set "a_float=1.1111"
workflow_run_ok "${TEST_NAME_BASE}-run" \
    cylc play --debug "${WORKFLOW_NAME}" --pause\
    --set "a_str='foo'" --set "an_int=24" --set "a_float=1.1111"

sqlite3 "${WORKFLOW_RUN_DIR}/log/db" 'SELECT * FROM workflow_template_vars' >'sqlite3.out'

# Chop the bottom of the file off to avoid issues with Cylc Version.
head -n 3 sqlite3.out > sqlite3.out2

cylc stop "${WORKFLOW_NAME}"

workflow_run_ok "${TEST_NAME_BASE}-restart" \
    cylc play --debug --no-detach "${WORKFLOW_NAME}"
#-------------------------------------------------------------------------------
purge
exit
