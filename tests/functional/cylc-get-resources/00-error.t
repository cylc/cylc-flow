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
# Cylc get-resources doesn't overwrite a file with a dir, or vice-versa:

. "$(dirname "$0")/test_header"
set_test_number 4

TEST="${TEST_NAME_BASE}-overwrite-dir"
mkdir cylc
run_fail "${TEST}" cylc get-resources cylc
grep_ok "Destination file is already directory" "${TEST}.stderr"
rm -r cylc

touch syntax
run_fail "${TEST}" cylc get-resources syntax
grep_ok "Destination directory is already a file" "${TEST}.stderr"

exit
