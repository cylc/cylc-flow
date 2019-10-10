#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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
# Test all current non-silent suite obsoletions and deprecations.
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 2
#-------------------------------------------------------------------------------
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-val"
run_ok "${TEST_NAME}" cylc validate -v "${SUITE_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-cmp
cylc validate -v "${SUITE_NAME}" 2>&1 \
    | sed  -n -e 's/^WARNING - \( \* (.*$\)/\1/p' > 'val.out'
cmp_ok val.out <<__END__
 * (8.0.0) [suite host self-identification] -> [suite run platforms][suite host self-identification] - value unchanged
 * (8.0.0) [suite servers] -> [suite run platforms] - value unchanged
 * (8.0.0) [cylc] -> [general] - value unchanged
 * (8.0.0) [scheduling][dependencies][X][graph] -> [scheduling][graph][X] - for X in:
__END__
#-------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"
