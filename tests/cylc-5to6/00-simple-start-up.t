#!/bin/bash
#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 NIWA
#C:
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.
#-------------------------------------------------------------------------------
# Test cat-view with a Jinja2 variable defined in a single cylc include-file
# TODO - another test for nested file inclusion
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 5
install_suite $TEST_NAME_BASE $TEST_NAME_BASE
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-validate
run_ok "$TEST_NAME" cylc validate $SUITE_NAME
sed -n '/REPLACING .* DEPENDENCIES/,/^"""/p' "$TEST_NAME.stdout" \
    >"$TEST_NAME.dep-replace"
cmp_ok "$TEST_NAME.dep-replace" <<'__DEP_INFO__'
# REPLACING START-UP/ASYNC DEPENDENCIES WITH AN R1* SECTION
# (VARYING INITIAL CYCLE POINT MAY AFFECT VALIDITY)
        [[[R1]]]
            graph = """
cold_foo
cold_foo => foo_midnight
cold_foo => foo_twelves
"""
# REPLACING START-UP/ASYNC DEPENDENCIES WITH AN R1* SECTION
# (VARYING INITIAL CYCLE POINT MAY AFFECT VALIDITY)
        [[[R1/2014010106]]]
            graph = """
cold_foo[^] => foo_dawn
"""
__DEP_INFO__
#-------------------------------------------------------------------------------
# Run the convert-suggest-tool.
TEST_NAME=$TEST_NAME_BASE-5to6
run_ok "$TEST_NAME" cylc 5to6 "$TEST_DIR/$SUITE_NAME/suite.rc"
cmp_ok "$TEST_NAME.stdout" <<'__OUT__'
description = Simple cylc 5 suite using start-up tasks.
title = Simple start-up suite.
[cylc]
    abort if any task fails = False
    log resolved dependencies = False
    UTC mode = True
    [[dummy mode]]
        disable suite event hooks = True
    [[event hooks]]
        timeout = P1D # UPGRADE CHANGE: ISO 8601 durations
        timeout handler = true
        abort if timeout handler fails = False
    [[reference test]]
        live mode suite timeout = PT2H # UPGRADE CHANGE: ISO 8601 durations
        dummy mode suite timeout = PT1H # UPGRADE CHANGE: ISO 8601 durations
        simulation mode suite timeout = PT1H # UPGRADE CHANGE: ISO 8601 durations
[scheduling]
    initial cycle point = 20140101T00 # UPGRADE CHANGE: ISO 8601, 'time' -> 'point'
    final cycle point = 20140104T00 # UPGRADE CHANGE: ISO 8601, 'time' -> 'point'
    runahead limit = PT6H # UPGRADE CHANGE: ISO 8601 cycle duration
    [[dependencies]]
        [[[T00]]] # UPGRADE CHANGE: ISO 8601-like recurrence abbreviations
            graph = foo_midnight[-P1D] & cold_foo => foo_midnight # UPGRADE CHANGE: offset as ISO 8601 duration (assume hourly cycling)
        [[[T00, T12]]] # UPGRADE CHANGE: ISO 8601-like recurrence abbreviations
            graph = foo_twelves[-PT12H] & cold_foo => foo_twelves # UPGRADE CHANGE: offset as ISO 8601 duration (assume hourly cycling)
        [[[T06]]] # UPGRADE CHANGE: ISO 8601-like recurrence abbreviations
            graph = foo_dawn[-P1D] & cold_foo => foo_dawn # UPGRADE CHANGE: offset as ISO 8601 duration (assume hourly cycling)
        [[[Daily(20131231 ,2)  ]]]  # UPGRADE INFO: manually convert. [[[P2D]]]?
            # UPGRADE INFO: change any mistaken [-PTnH] to [-PnD].
            graph = "foo_d => bar_d" 
        [[[Monthly(201402,1)]]]  # UPGRADE INFO: manually convert. [[[P1M]]]?
            # UPGRADE INFO: change any mistaken [-PTnH] to [-PnM].
            graph = "foo_m[-PT2H] => bar_m & foo_m"  # UPGRADE CHANGE: offset as ISO 8601 duration (assume hourly cycling)
        [[[  Yearly( 2010 , 3 ) ]]]  # UPGRADE INFO: manually convert. [[[P3Y]]]?
            # UPGRADE INFO: change any mistaken [-PTnH] to [-PnY].
            graph = "foo_y => bar_y"
    [[special tasks]]
        start-up = cold_foo # UPGRADE INFO: Replace this and *all* start-up/async graph deps with 'cylc validate' 'R1*' output
[runtime]
    [[root]]
        command scripting = true
        retry delays = PT0.5M, PT10M, PT30M, 5*PT1H, 2*PT3H, P1D # UPGRADE CHANGE: delays as ISO 8601 durations
        [[[event hooks]]]
            execution timeout = PT3H # UPGRADE CHANGE: ISO 8601 durations
            submission timeout = PT6H # UPGRADE CHANGE: ISO 8601 durations
        [[[suite state polling]]]
            interval = PT5S # UPGRADE CHANGE: ISO 8601 durations
        [[[job submission]]]
            shell = /bin/bash
            command template = 
            method = background
            retry delays = PT5M # UPGRADE CHANGE: delays as ISO 8601 durations
[visualization]
    initial cycle point = 20140101T00
    final cycle point = 20140102T06
__OUT__
cmp_ok "$TEST_NAME.stderr" </dev/null
#-------------------------------------------------------------------------------
#purge_suite $SUITE_NAME
exit
