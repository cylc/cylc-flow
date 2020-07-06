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
 * (6.1.3) [visualization][enable live graph movie] - DELETED (OBSOLETE)
 * (7.2.2) [cylc][dummy mode] - DELETED (OBSOLETE)
 * (7.2.2) [cylc][simulation mode] - DELETED (OBSOLETE)
 * (7.2.2) [runtime][foo, cat, dog][dummy mode] - DELETED (OBSOLETE)
 * (7.2.2) [runtime][foo, cat, dog][simulation mode] - DELETED (OBSOLETE)
 * (7.6.0) [runtime][foo, cat, dog][enable resurrection] - DELETED (OBSOLETE)
 * (7.8.0) [runtime][foo, cat, dog][suite state polling][template] - DELETED (OBSOLETE)
 * (7.8.1) [cylc][events][reset timer] - DELETED (OBSOLETE)
 * (7.8.1) [cylc][events][reset inactivity timer] - DELETED (OBSOLETE)
 * (7.8.1) [runtime][foo, cat, dog][events][reset timer] - DELETED (OBSOLETE)
__END__

purge_suite "${SUITE_NAME}"
