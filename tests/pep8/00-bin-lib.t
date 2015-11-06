#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2015 NIWA
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
# Test compliance with PEP8.
. "$(dirname "$0")/test_header"

if ! pep8 --version 1>'/dev/null' 2>&1; then
    skip_all '"pep8" command not available'
fi

set_test_number 3

run_ok "${TEST_NAME_BASE}" pep8 \
    "${CYLC_DIR}/lib/cylc" \
    $(grep -l '#!.*\<python\>' "${CYLC_DIR}/bin/"*)
cmp_ok "${TEST_NAME_BASE}.stdout" <'/dev/null'
cmp_ok "${TEST_NAME_BASE}.stderr" <'/dev/null'

exit
