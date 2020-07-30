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

# Test consecutive spaces in a __MANY__ name fails validation (GitHub #2417).

. "$(dirname "$0")/test_header"
set_test_number 2

TEST_NAME="${TEST_NAME_BASE}-val"
cat > suite.rc <<__END__
[scheduling]
    [[graph]]
        R1 = task1
 [runtime]
     [[HPC]]
        [[[job]]]
           batch system = pbs
        [[[directives]]]
           -l select=1:ncpus=1:mem=5GB
     [[task1]]
        inherit = HPC
        [[[directives]]]
            -l  select=1:ncpus=24:mem=20GB  # ERROR!
__END__
run_fail "${TEST_NAME}" cylc validate suite.rc
cmp_ok "${TEST_NAME}.stderr" <<__END__
IllegalItemError: [runtime][task1][directives]-l  select - (consecutive spaces)
__END__
