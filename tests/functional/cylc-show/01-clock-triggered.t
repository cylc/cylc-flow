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
# Test cylc show for a clock triggered task
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 3
#-------------------------------------------------------------------------------
install_workflow "${TEST_NAME_BASE}" clock-triggered
#-------------------------------------------------------------------------------
TEST_SHOW_OUTPUT_PATH="$PWD/${TEST_NAME_BASE}-show.stdout"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate \
    --set="TEST_OUTPUT_PATH='$TEST_SHOW_OUTPUT_PATH'" "${WORKFLOW_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-run"
workflow_run_ok "${TEST_NAME}" cylc play --reference-test --debug --no-detach \
    --set="TEST_OUTPUT_PATH='$TEST_SHOW_OUTPUT_PATH'" "${WORKFLOW_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-show
contains_ok "${TEST_NAME}.stdout" <<__SHOW_OUTPUT__
title: (not given)
description: (not given)
URL: (not given)

prerequisites (- => not satisfied):
  + 20141106T0900Z/woo succeeded

outputs (- => not completed):
  - 20141106T0900Z/foo expired
  + 20141106T0900Z/foo submitted
  - 20141106T0900Z/foo submit-failed
  + 20141106T0900Z/foo started
  - 20141106T0900Z/foo succeeded
  - 20141106T0900Z/foo failed

other (- => not satisfied):
  + Clock trigger time reached
  o Triggers at ... 2014-11-06T09:05:00Z
__SHOW_OUTPUT__
#-------------------------------------------------------------------------------
purge
