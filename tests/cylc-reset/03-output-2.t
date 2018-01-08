#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA
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
# Test "cylc reset --output='!OUTPUT' 'SUITE' 'TASK.ID'".
. "$(dirname "$0")/test_header"

set_test_number 3
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
run_ok "${TEST_NAME_BASE}" cylc run --reference-test --debug --no-detach "${SUITE_NAME}"
cmp_ok "${SUITE_RUN_DIR}/cylc-show.out" <<'__OUT__'
title: (not given)
description: (not given)
URL: (not given)

prerequisites (- => not satisfied):
  (None)

outputs (- => not completed):
  + t1.1 submitted
  + t1.1 started
  + t1.1 succeeded
  - t1.1 Greet World
  - t1.1 Hello World
__OUT__
purge_suite "${SUITE_NAME}"
exit
