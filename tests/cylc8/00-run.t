#!/bin/bash
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
# Cylc 7 should not run a Cylc 8 workflow

. "$(dirname "$0")/test_header"
set_test_number 3

SUITE_NAME="cylctb-${CYLC_TEST_TIME_INIT}/${TEST_SOURCE_DIR_BASE}/${TEST_NAME_BASE}"
SUITE_RUN_DIR="$(cylc get-global-config --print-run-dir)/${SUITE_NAME}"
mkdir -p "$SUITE_RUN_DIR"
cat > "${SUITE_RUN_DIR}/flow.cylc" << __FLOW__
# Darmok and Jalad at Tanagra
__FLOW__

TEST_NAME="${TEST_NAME_BASE}-fail"
suite_run_fail "$TEST_NAME" cylc run "$SUITE_NAME"

CYLC_TEST_DIFF_CMD="diff -u -Z" cmp_ok "${TEST_NAME}.stderr" << __EOF__
ERROR: Cannot run - flow.cylc (Cylc 8) file detected in suite run dir.
__EOF__

exists_fail "${SUITE_RUN_DIR}/.service"

rm -r "$SUITE_RUN_DIR"
rm -d "$TEST_SOURCE_DIR_BASE" 2> /dev/null || true
exit
