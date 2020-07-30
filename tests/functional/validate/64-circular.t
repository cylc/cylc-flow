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
# Test validation of a suite with self-edges fails.
. "$(dirname "$0")/test_header"

set_test_number 13

cat >'suite.rc' <<'__SUITE_RC__'
[scheduling]
    [[graph]]
        R1 = a => a
__SUITE_RC__

run_fail "${TEST_NAME_BASE}-simple-1" cylc validate 'suite.rc'
contains_ok "${TEST_NAME_BASE}-simple-1.stderr" <<'__ERR__'
SuiteConfigError: self-edge detected: a:succeed => a
__ERR__

cat >'suite.rc' <<'__SUITE_RC__'
[scheduling]
    [[graph]]
        R1 = a => b => c => d => a => z
__SUITE_RC__

run_fail "${TEST_NAME_BASE}-simple-2" cylc validate 'suite.rc'
contains_ok "${TEST_NAME_BASE}-simple-2.stderr" <<'__ERR__'
SuiteConfigError: circular edges detected:  d.1 => a.1  a.1 => b.1  b.1 => c.1  c.1 => d.1
__ERR__

cat >'suite.rc' <<'__SUITE_RC__'
[scheduling]
    [[graph]]
        R1 = FAM:succeed-all => f & g => z
[runtime]
    [[FAM]]
    [[f,g,h]]
       inherit = FAM
__SUITE_RC__

run_fail "${TEST_NAME_BASE}-simple-fam" cylc validate 'suite.rc'
contains_ok "${TEST_NAME_BASE}-simple-fam.stderr" <<'__ERR__'
SuiteConfigError: self-edge detected: f:succeed => f
__ERR__

cat >'suite.rc' <<'__SUITE_RC__'
[cylc]
    cycle point format = %Y
[scheduling]
    initial cycle point = 2001
    final cycle point = 2010
    [[graph]]
        P1Y = '''
a[-P1Y] => a
a[+P1Y] => a
'''
__SUITE_RC__

run_fail "${TEST_NAME_BASE}-intercycle-1" cylc validate 'suite.rc'
contains_ok "${TEST_NAME_BASE}-intercycle-1.stderr" <<'__ERR__'
SuiteConfigError: circular edges detected:  a.2002 => a.2001  a.2001 => a.2002  a.2003 => a.2002  a.2002 => a.2003
__ERR__

cat >'suite.rc' <<'__SUITE_RC__'
[scheduling]
    cycling mode = integer
    initial cycle point = 1
    [[graph]]
        2/P3 = foo => bar => baz
        8/P1 = baz => foo
__SUITE_RC__

run_fail "${TEST_NAME_BASE}-intercycle-2" cylc validate 'suite.rc'
contains_ok "${TEST_NAME_BASE}-intercycle-2.stderr" <<'__ERR__'
SuiteConfigError: circular edges detected:  foo.8 => bar.8  bar.8 => baz.8  baz.8 => foo.8
__ERR__

cat >'suite.rc' <<'__SUITE_RC__'
[cylc]
    [[parameters]]
        foo = 1..5
[scheduling]
    [[graph]]
        R1 = """
            fool<foo-1> => fool<foo>
            fool<foo=2> => fool<foo=1>
        """
__SUITE_RC__

run_fail "${TEST_NAME_BASE}-param-1" cylc validate 'suite.rc'
contains_ok "${TEST_NAME_BASE}-param-1.stderr" <<'__ERR__'
SuiteConfigError: circular edges detected:  fool_foo2.1 => fool_foo1.1  fool_foo1.1 => fool_foo2.1
__ERR__

cat >'suite.rc' <<'__SUITE_RC__'
[scheduling]
    cycling mode = integer
    initial cycle point = 1
    [[graph]]
        1/P3 = foo => bar
        2/P3 = bar => foo
__SUITE_RC__

run_ok "${TEST_NAME_BASE}-param-2" cylc validate 'suite.rc'

exit
