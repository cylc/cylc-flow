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

# Check Cylc 7 backward compatibility for success/fail branching.

# A bunch of unit tests in test_graph_parser.py check that outputs are handled
# the same for a wide variety of graphs. This functional test should be
# sufficient to check the resulting validation and run time behaviour.

. "$(dirname "$0")/test_header"
set_test_number 7aul

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

TEST_NAME="${TEST_NAME_BASE}-validate_as_c8"
run_fail "${TEST_NAME}" cylc validate "${WORKFLOW_NAME}"

cmp_ok ${TEST_NAME}.stderr <<__ERR__
GraphParseError: Output foo:succeeded is required so \
foo:failed can't also be required.
__ERR__

# Rename config to "suite.rc"
mv ${WORKFLOW_RUN_DIR}/flow.cylc ${WORKFLOW_RUN_DIR}/suite.rc
ln -s ${WORKFLOW_RUN_DIR}/suite.rc ${WORKFLOW_RUN_DIR}/flow.cylc 

# It should now validate, with a deprecation message
TEST_NAME="${TEST_NAME_BASE}-validate_as_c7"
run_ok "${TEST_NAME}" cylc validate "${WORKFLOW_NAME}"

DEPR_MSG=$(python -c \
  'from cylc.flow.workflow_files import SUITERC_DEPR_MSG; \
      print(SUITERC_DEPR_MSG)')
grep_ok "${DEPR_MSG}" "${TEST_NAME}.stderr"

contains_ok "${TEST_NAME}.stderr" <<__ERR__
WARNING - Output foo:succeeded is required so \
foo:failed can't also be required.
__ERR__

grep_ok "making both optional." "${TEST_NAME}.stderr"

# And it should run without stalling with an incomplete task.
workflow_run_ok "${TEST_NAME_BASE}-run" \
    cylc play -n --reference-test --debug "${WORKFLOW_NAME}"

purge
exit
