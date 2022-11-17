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
# Test include-file inlining
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 3
#-------------------------------------------------------------------------------
install_workflow "${TEST_NAME_BASE}" workflow
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate"
# test raw workflow validates
run_ok "${TEST_NAME}.1" cylc validate "${WORKFLOW_NAME}"

# test workflow validates as inlined during editing
mkdir inlined
cylc view --inline "${WORKFLOW_NAME}" > inlined/flow.cylc
run_ok "${TEST_NAME}.2" cylc validate ./inlined
#-------------------------------------------------------------------------------
# compare inlined workflow def with reference copy
TEST_NAME=${TEST_NAME_BASE}-compare
cmp_ok inlined/flow.cylc "${TEST_SOURCE_DIR}/workflow/ref-inlined.cylc"
rm -rf inlined
#-------------------------------------------------------------------------------
purge
#-------------------------------------------------------------------------------
