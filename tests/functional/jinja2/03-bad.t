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
#------------------------------------------------------------------------------
# Test Jinja2 errors
# Ensure parsec can pull out the context lines even when they are behind
# an include statement

. "$(dirname "$0")/test_header"
set_test_number 10

sub_tabs() {
    sed -i 's/\t/ /g' "${TEST_NAME}.stderr"
}

purge_workflow() {
    if ((FAILURES != 0)); then
        exit
    fi
    purge
}

#------------------------------------------------------------------------------
# Test syntax error in flow.cylc
install_workflow "${TEST_NAME_BASE}" badsyntax

TEST_NAME="${TEST_NAME_BASE}-badsyntax"
run_fail "${TEST_NAME}" cylc validate "${WORKFLOW_NAME}"

sub_tabs
cmp_ok "${TEST_NAME}.stderr" <<__HERE__
Jinja2Error: Expected an expression, got 'end of statement block'
File ${WORKFLOW_RUN_DIR}/flow.cylc
  #!Jinja2
  # line before
  {% set x = %} <-- TemplateSyntaxError
__HERE__

purge_workflow

#------------------------------------------------------------------------------
# Test syntax error in an include file
install_workflow "${TEST_NAME_BASE}" include-badsyntax

TEST_NAME="${TEST_NAME_BASE}-include-badsyntax"
run_fail "${TEST_NAME}" cylc validate "${WORKFLOW_NAME}"

sub_tabs
cmp_ok "${TEST_NAME}.stderr" <<__HERE__
Jinja2Error: unexpected char '"' at 142
Error in file "runtime-bad.cylc"
File ${WORKFLOW_RUN_DIR}/runtime-bad.cylc
      [[FAM]]
          [[[environment]]]
              TITLE="member"
  {%- for num in ["0","1","2","3",4"] %} <-- TemplateSyntaxError
File ${WORKFLOW_RUN_DIR}/flow.cylc
      [[graph]]
          R1 = "a => FAM"
  [runtime]
  {% include 'runtime-bad.cylc' %} <-- TemplateSyntaxError
__HERE__

purge_workflow

#------------------------------------------------------------------------------
# Test syntax error in an include file (included using the Cylc built-in
# %include keyword)
install_workflow "${TEST_NAME_BASE}" cylc-include-badsyntax

TEST_NAME="${TEST_NAME_BASE}-cylc-include-badsyntax"
run_fail "${TEST_NAME}" cylc validate "${WORKFLOW_NAME}"

sub_tabs
cmp_ok "${TEST_NAME}.stderr" <<__HERE__
Jinja2Error: Encountered unknown tag 'end'.
Jinja was looking for the following tags: 'elif' or 'else' or 'endif'.
The innermost block that needs to be closed is 'if'.
File ${WORKFLOW_RUN_DIR}/flow.cylc
  # This is a bit of graph configuration.
          {% if true %}
          R1 = foo
          {% end if % <-- TemplateSyntaxError
__HERE__

purge_workflow

#------------------------------------------------------------------------------
# Test missing include file
install_workflow "${TEST_NAME_BASE}" include-missing

TEST_NAME="${TEST_NAME_BASE}-include-missing"
run_fail "${TEST_NAME}" cylc validate "${WORKFLOW_NAME}"

sub_tabs
cmp_ok "${TEST_NAME}.stderr" <<__HERE__
Jinja2Error: runtime.cylc
File ${WORKFLOW_RUN_DIR}/flow.cylc
      [[graph]]
          R1 = "a => FAM"
  [runtime]
  {% include 'runtime.cylc' %} <-- TemplateNotFound
__HERE__

purge_workflow

#------------------------------------------------------------------------------
# Test incomplete loop
install_workflow "${TEST_NAME_BASE}" include-incomplete

TEST_NAME="${TEST_NAME_BASE}-include-incomplete"
run_fail "${TEST_NAME}" cylc validate "${WORKFLOW_NAME}"

sub_tabs
cmp_ok "${TEST_NAME}.stderr" << __HERE__
Jinja2Error: Unexpected end of template.
Error in file "runtime-incomplete.cylc"
Jinja was looking for the following tags: 'endfor' or 'else'. The
innermost block that needs to be closed is 'for'.
File ${WORKFLOW_RUN_DIR}/runtime-incomplete.cylc
  {%- for num in range(5) %}
      [[member_{{ num }}]]
          inherit = FAM
          script = echo I am \$TITLE {{ num }} <-- TemplateSyntaxError
File ${WORKFLOW_RUN_DIR}/flow.cylc
      [[graph]]
          R1 = "a => FAM"
  [runtime]
  {% include 'runtime-incomplete.cylc' %} <-- TemplateSyntaxError
__HERE__

purge_workflow
