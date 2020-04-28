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
# Test repeated item override and repeated graph string merge 
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 7
#-------------------------------------------------------------------------------
install_suite "${TEST_NAME_BASE}" one
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${SUITE_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-a
cylc get-config -i [meta]title "${SUITE_NAME}" >a.txt 2>/dev/null
cmp_ok a.txt <<'__END'
the quick brown fox
__END
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-b"
cylc get-config -i '[scheduling][graph]R1' "${SUITE_NAME}" | sort \
    >'b.txt' 2>'/dev/null'
cmp_ok 'b.txt' <<'__END'
bar => baz
foo => bar
__END
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-c"
cylc get-config -i '[scheduling][graph]T00' "${SUITE_NAME}" | sort \
    >'c.txt' 2>'/dev/null'
cmp_ok 'c.txt' <<'__END'
cbar => cbaz
cfoo => cbar
dbar => dbaz
dfoo => dbar
__END
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-d
cylc get-config -i '[runtime][FOO][meta]title' "${SUITE_NAME}" >d.txt 2>/dev/null
cmp_ok d.txt <<'__END'
the quick brown fox
__END
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-e
cylc get-config -i '[runtime][FOO][meta]description' "${SUITE_NAME}" >e.txt 2>/dev/null
cmp_ok e.txt <<'__END'
jumped over the lazy dog
__END
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-f
cylc get-config -i '[runtime][FOO][environment]' "${SUITE_NAME}" >f.txt 2>/dev/null
cmp_ok f.txt <<'__END'
VAR1 = the quick brown fox
__END
#-------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"
