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
set_test_number 3
#-------------------------------------------------------------------------------
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
TEST_SHOW_OUTPUT_PATH="$PWD/${TEST_NAME_BASE}-show.stdout"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate \
   --set=TEST_OUTPUT_PATH="$TEST_SHOW_OUTPUT_PATH"  "${SUITE_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-run"
run_ok "${TEST_NAME}" cylc run \
   --no-detach --set=TEST_OUTPUT_PATH="$TEST_SHOW_OUTPUT_PATH" "${SUITE_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-show"
contains_ok "${TEST_SHOW_OUTPUT_PATH}" << '__OUT__'
title: (not given)
description: (not given)
URL: (not given)

prerequisites (- => not satisfied):
  + ((0  &  1)  &  (2  |  (3  &  4)))
  + 	0 = a.20000101T0000Z succeeded
  + 	1 = b.20000101T0000Z succeeded
  + 	2 = c.20000101T0000Z succeeded
  + 	3 = d.20000101T0000Z succeeded
  + 	4 = e.20000101T0000Z succeeded

outputs (- => not completed):
  - f.20000101T0000Z expired
  + f.20000101T0000Z submitted
  - f.20000101T0000Z submit-failed
  + f.20000101T0000Z started
  - f.20000101T0000Z succeeded
  - f.20000101T0000Z failed
a.20000101T0000Z succeeded
b.20000101T0000Z succeeded
c.20000101T0000Z succeeded
d.20000101T0000Z succeeded
e.20000101T0000Z succeeded
title: (not given)
description: (not given)
URL: (not given)

prerequisites (- => not satisfied):
  + 0 & 1 & (2 | (3 & 4)) & 5
  + 	0 = a.20000102T0000Z succeeded
  + 	1 = b.20000102T0000Z succeeded
  + 	2 = c.20000102T0000Z succeeded
  + 	3 = d.20000102T0000Z succeeded
  + 	4 = e.20000102T0000Z succeeded
  + 	5 = f.20000101T0000Z succeeded

outputs (- => not completed):
  - f.20000102T0000Z expired
  + f.20000102T0000Z submitted
  - f.20000102T0000Z submit-failed
  + f.20000102T0000Z started
  - f.20000102T0000Z succeeded
  - f.20000102T0000Z failed
a.20000102T0000Z succeeded
b.20000102T0000Z succeeded
c.20000102T0000Z succeeded
d.20000102T0000Z succeeded
e.20000102T0000Z succeeded
f.20000101T0000Z succeeded
__OUT__
#-------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"
