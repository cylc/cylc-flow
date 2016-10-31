#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2016 NIWA
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
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 2
#-------------------------------------------------------------------------------
install_suite $TEST_NAME_BASE $TEST_NAME_BASE
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-val
run_ok $TEST_NAME cylc validate -v $SUITE_NAME
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-cmp
cylc validate -v "${SUITE_NAME}" 2>&1 \
    | sed \
    -e "1,/WARNING: deprecated items were automatically upgraded in 'suite/d;" \
    -e '/Expanding \[runtime\] namespace lists and parameters/,$d' \
    > 'val.out'
cmp_ok val.out <<__END__
 * (6.1.3) [visualization][enable live graph movie] - DELETED (OBSOLETE)
 * (6.4.0) [runtime][foo, cat, dog][environment scripting] -> [runtime][foo, cat, dog][env-script] - value unchanged
 * (6.4.0) [runtime][foo, cat, dog][initial scripting] -> [runtime][foo, cat, dog][init-script] - value unchanged
 * (6.4.0) [runtime][foo, cat, dog][post-command scripting] -> [runtime][foo, cat, dog][post-script] - value unchanged
 * (6.4.0) [runtime][foo, cat, dog][pre-command scripting] -> [runtime][foo, cat, dog][pre-script] - value unchanged
 * (6.4.0) [runtime][foo, cat, dog][command scripting] -> [runtime][foo, cat, dog][script] - value unchanged
 * (6.4.0) [runtime][foo, cat, dog][dummy mode][command scripting] -> [runtime][foo, cat, dog][dummy mode][script] - value unchanged
 * (6.5.0) [scheduling][special tasks][clock-triggered] -> [scheduling][special tasks][clock-trigger] - value unchanged
 * (6.5.0) [scheduling][special tasks][external-triggered] -> [scheduling][special tasks][external-trigger] - value unchanged
 * (6.11.0) [runtime][foo, cat, dog][event hooks][retry handler] -> [runtime][foo, cat, dog][events][retry handler] - value unchanged
 * (6.11.0) [runtime][foo, cat, dog][job submission][method] -> [runtime][foo, cat, dog][job][batch system] - value unchanged
 * (6.11.0) [runtime][foo, cat, dog][job submission][command template] -> [runtime][foo, cat, dog][job][batch submit command template] - value unchanged
 * (6.11.0) [runtime][foo, cat, dog][job submission][retry delays] -> [runtime][foo, cat, dog][job][submission retry delays] - value unchanged
 * (6.11.0) [runtime][foo, cat, dog][retry delays] -> [runtime][foo, cat, dog][job][execution retry delays] - value unchanged
 * (6.11.0) [runtime][foo, cat, dog][submission polling intervals] -> [runtime][foo, cat, dog][job][submission polling intervals] - value unchanged
 * (6.11.0) [runtime][foo, cat, dog][execution polling intervals] -> [runtime][foo, cat, dog][job][execution polling intervals] - value unchanged
__END__
#-------------------------------------------------------------------------------
purge_suite $SUITE_NAME
