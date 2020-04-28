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
# Check tasks and graph generated by parameter expansion.
. "$(dirname "$0")/test_header"
set_test_number 39

cat >'suite.rc' <<'__SUITE__'
[cylc]
    [[parameters]]
        i = cat, dog, fish
        j = 1..5
        k = 1..10..4
[scheduling]
    [[graph]]
        R1 = """
foo<i> => bar<j>
qux<j> => waz<k>
"""
[runtime]
    [[root]]
        script = true
    [[foo<i>]]
    [[bar<j>]]
    [[qux<j>]]
    [[waz<k>]]
__SUITE__
run_ok "${TEST_NAME_BASE}-01" cylc validate "suite.rc"
cylc graph --reference 'suite.rc' >'01.graph'
cmp_ok "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/01.graph.ref" '01.graph'

cat >'suite.rc' <<'__SUITE__'
[cylc]
    [[parameters]]
        i = 25, 30..35, 1..5, 110
[scheduling]
    [[graph]]
        R1 = """
foo<i> => bar<i>
"""
[runtime]
    [[root]]
        script = true
    [[foo<i>]]
    [[bar<i>]]
__SUITE__
run_ok "${TEST_NAME_BASE}-02" cylc validate "suite.rc"
cylc graph --reference 'suite.rc' >'02.graph'
cmp_ok "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/02.graph.ref" '02.graph'

cat >'suite.rc' <<'__SUITE__'
[cylc]
    [[parameters]]
        i = a-t, c-g
[scheduling]
    [[graph]]
        R1 = """
foo<i> => bar<i>
"""
[runtime]
    [[root]]
        script = true
    [[foo<i>]]
    [[bar<i>]]
__SUITE__
run_ok "${TEST_NAME_BASE}-03" cylc validate "suite.rc"
cylc graph --reference 'suite.rc' >'03.graph'
cmp_ok "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/03.graph.ref" '03.graph'

cat >'suite.rc' <<'__SUITE__'
[cylc]
    [[parameters]]
        i = 100, hundred, one-hundred, 99+1
[scheduling]
    [[graph]]
        R1 = """
foo<i> => bar<i>
"""
[runtime]
    [[root]]
        script = true
    [[foo<i>]]
    [[bar<i>]]
__SUITE__
run_ok "${TEST_NAME_BASE}-04" cylc validate "suite.rc"
cylc graph --reference 'suite.rc' >'04.graph'
cmp_ok "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/04.graph.ref" '04.graph'

cat >'suite.rc' <<'__SUITE__'
[cylc]
    [[parameters]]
        i = space is dangerous
[scheduling]
    [[graph]]
        R1 = """
foo<i> => bar<i>
"""
[runtime]
    [[root]]
        script = true
    [[foo<i>]]
    [[bar<i>]]
__SUITE__
run_fail "${TEST_NAME_BASE}-05" cylc validate "suite.rc"
cmp_ok "${TEST_NAME_BASE}-05.stderr" <<'__ERR__'
IllegalValueError: (type=parameter) [cylc][parameters]i = space is dangerous - (space is dangerous: bad value)
__ERR__

cat >'suite.rc' <<'__SUITE__'
[cylc]
    [[parameters]]
        i = mix, 1..10
[scheduling]
    [[graph]]
        R1 = """
foo<i> => bar<i>
"""
[runtime]
    [[root]]
        script = true
    [[foo<i>]]
    [[bar<i>]]
__SUITE__
run_fail "${TEST_NAME_BASE}-06" cylc validate "suite.rc"
cmp_ok "${TEST_NAME_BASE}-06.stderr" <<'__ERR__'
IllegalValueError: (type=parameter) [cylc][parameters]i = mix, 1..10 - (mixing int range and str)
__ERR__

cat >'suite.rc' <<'__SUITE__'
[cylc]
    [[parameters]]
        i = a, b #, c, d, e  # comment
[scheduling]
    [[graph]]
        R1 = """
foo<i> => bar<i>
"""
[runtime]
    [[root]]
        script = true
    [[foo<i>]]
    [[bar<i>]]
__SUITE__
run_ok "${TEST_NAME_BASE}-07" cylc validate "suite.rc"
cylc graph --reference 'suite.rc' >'07.graph'
cmp_ok "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/07.graph.ref" '07.graph'

cat >'suite.rc' <<'__SUITE__'
[cylc]
    [[parameters]]
        i = 1..2 3..4
[scheduling]
    [[graph]]
        R1 = """
foo<i> => bar<i>
"""
[runtime]
    [[root]]
        script = true
    [[foo<i>]]
    [[bar<i>]]
__SUITE__
run_fail "${TEST_NAME_BASE}-08" cylc validate "suite.rc"
cmp_ok "${TEST_NAME_BASE}-08.stderr" <<'__ERR__'
IllegalValueError: (type=parameter) [cylc][parameters]i = 1..2 3..4 - (1..2 3..4: bad value)
__ERR__

cat >'suite.rc' <<'__SUITE__'
[cylc]
    [[parameters]]
        i =
[scheduling]
    [[graph]]
        R1 = """
foo<i> => bar<i>
"""
[runtime]
    [[root]]
        script = true
    [[foo<i>]]
    [[bar<i>]]
__SUITE__
run_fail "${TEST_NAME_BASE}-09" cylc validate "suite.rc"
cmp_ok "${TEST_NAME_BASE}-09.stderr" <<'__ERR__'
ParamExpandError: parameter i is not defined in foo<i>
__ERR__

cat >'suite.rc' <<'__SUITE__'
[scheduling]
    [[graph]]
        R1 = """
foo<i> => bar<i>
"""
[runtime]
    [[root]]
        script = true
    [[foo<i>]]
    [[bar<i>]]
__SUITE__
run_fail "${TEST_NAME_BASE}-10" cylc validate "suite.rc"
cmp_ok "${TEST_NAME_BASE}-10.stderr" <<'__ERR__'
ParamExpandError: parameter i is not defined in <i>: foo<i>=>bar<i>
__ERR__

cat >'suite.rc' <<'__SUITE__'
[cylc]
    [[parameters]]
        j = +1..+5
    [[parameter templates]]
        j = @%(j)03d
[scheduling]
    [[graph]]
        R1 = "foo<j> => bar<j>"
[runtime]
    [[root]]
        script = true
    [[foo<j>]]
    [[bar<j>]]
__SUITE__
run_ok "${TEST_NAME_BASE}-11" cylc validate "suite.rc"
cylc graph --reference 'suite.rc' >'11.graph'
cmp_ok "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/11.graph.ref" '11.graph'

cat >'suite.rc' <<'__SUITE__'
[cylc]
    [[parameters]]
        j = 1..5
    [[parameter templates]]
        j = +%%j%(j)03d
[scheduling]
    [[graph]]
        R1 = "foo<j> => bar<j>"
[runtime]
    [[root]]
        script = true
    [[foo<j>]]
    [[bar<j>]]
__SUITE__
run_ok "${TEST_NAME_BASE}-12" cylc validate "suite.rc"
cylc graph --reference 'suite.rc' >'12.graph'
cmp_ok "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/12.graph.ref" '12.graph'

# Parameter with various meta characters
cat >'suite.rc' <<'__SUITE__'
[cylc]
    [[parameters]]
        p = -minus, +plus, @at, %percent
    [[parameter templates]]
        p = %(p)s
[scheduling]
    [[graph]]
        R1 = "foo<p> => bar<p>"
[runtime]
    [[root]]
        script = true
    [[foo<p>]]
    [[bar<p>]]
__SUITE__
run_ok "${TEST_NAME_BASE}-13" cylc validate "suite.rc"
cylc graph --reference 'suite.rc' >'13.graph'
cmp_ok "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/13.graph.ref" '13.graph'

# Parameter as task name
cat >'suite.rc' <<'__SUITE__'
[cylc]
    [[parameters]]
        i = 0..2
        s = mercury, venus, earth, mars
    [[parameter templates]]
        i = i%(i)d
        s = %(s)s
[scheduling]
    [[graph]]
        R1 = """
foo => <i> => bar
foo => <s> => bar
"""
[runtime]
    [[foo, bar, <i>, <s>]]
        script = true
__SUITE__
run_ok "${TEST_NAME_BASE}-14" cylc validate "suite.rc"
cylc graph --reference 'suite.rc' >'14.graph'
cmp_ok "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/14.graph.ref" '14.graph'

# Parameter in middle of family name
cat >'suite.rc' <<'__SUITE__'
[cylc]
    [[parameters]]
        s = mercury, venus, earth, mars
[scheduling]
    [[graph]]
        R1 = X<s>Y
[runtime]
    [[X<s>Y]]
        script = true
    [[x<s>y]]
        inherit = X<s>Y
__SUITE__
run_ok "${TEST_NAME_BASE}-15" cylc validate "suite.rc"
cylc graph --reference 'suite.rc' >'15.graph'
cmp_ok "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/15.graph.ref" '15.graph'

# -ve offset on RHS
cat >'suite.rc' <<'__SUITE__'
[cylc]
    [[parameters]]
        m = cat, dog
[scheduling]
    [[graph]]
        R1 = "foo<m> => foo<m-1>"
[runtime]
    [[root]]
        script = true
    [[foo<m>]]
__SUITE__
run_ok "${TEST_NAME_BASE}-16" cylc validate "suite.rc"
cylc graph --reference 'suite.rc' >'16.graph'
cmp_ok "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/16.graph.ref" '16.graph'

# +ve offset
cat >'suite.rc' <<'__SUITE__'
[cylc]
    [[parameters]]
        m = cat, dog
[scheduling]
    [[graph]]
        R1 = "foo<m> => foo<m+1>"
[runtime]
    [[root]]
        script = true
    [[foo<m>]]
__SUITE__
run_ok "${TEST_NAME_BASE}-17" cylc validate "suite.rc"
cylc graph --reference 'suite.rc' >'17.graph'
cmp_ok "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/17.graph.ref" '17.graph'

# Negative integers
cat >'suite.rc' <<'__SUITE__'
[cylc]
    [[parameters]]
        m = -12..12..6
[scheduling]
    [[graph]]
        R1 = "foo<m>"
[runtime]
    [[root]]
        script = true
    [[foo<m>]]
__SUITE__
run_ok "${TEST_NAME_BASE}-18" cylc validate "suite.rc"
cylc graph --reference 'suite.rc' >'18.graph'
cmp_ok "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/18.graph.ref" '18.graph'

# Reference by value, with -+ meta characters
cat >'suite.rc' <<'__SUITE__'
[cylc]
    [[parameters]]
        lang = c++, fortran-2008
    [[parameter templates]]
        lang = %(lang)s
[scheduling]
    [[graph]]
        R1 = "<lang=c++> => <lang = fortran-2008>"
[runtime]
    [[<lang>]]
        script = true
    [[<lang=c++>]]
        [[[environment]]]
            CC = gcc
    [[<lang = fortran-2008>]]
        [[[environment]]]
            FC = gfortran
__SUITE__
run_ok "${TEST_NAME_BASE}-19" cylc validate --debug "suite.rc"
cylc graph --reference 'suite.rc' >'19.graph'
cmp_ok "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/19.graph.ref" '19.graph'
# Note: This also demonstrates current badness of "cylc get-config"...
#       Inconsistence between graph/runtime whitespace handling.
#       Inconsistence between graph/runtime parameter expansion.
cylc get-config --sparse 'suite.rc' >'19.rc'
cmp_ok '19.rc' <<'__SUITERC__'
[cylc]
    [[parameters]]
        lang = c++, fortran-2008
    [[parameter templates]]
        lang = %(lang)s
[scheduling]
    cycling mode = integer
    initial cycle point = 1
    final cycle point = 1
    [[graph]]
        R1 = <lang=c++> => <lang = fortran-2008>
[runtime]
    [[root]]
    [[c++]]
        script = true
        [[[environment]]]
            CC = gcc
    [[fortran-2008]]
        script = true
        [[[environment]]]
            FC = gfortran
[visualization]
    [[node attributes]]
__SUITERC__

exit
