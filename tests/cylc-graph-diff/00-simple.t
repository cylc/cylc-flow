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
# Test cylc graph-diff for two suites.
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 24
#-------------------------------------------------------------------------------
install_suite $TEST_NAME_BASE-control $TEST_NAME_BASE-control
CONTROL_SUITE_NAME=$SUITE_NAME
install_suite $TEST_NAME_BASE-diffs $TEST_NAME_BASE-diffs
DIFF_SUITE_NAME=$SUITE_NAME
install_suite $TEST_NAME_BASE-same $TEST_NAME_BASE-same
SAME_SUITE_NAME=$SUITE_NAME
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-validate-diffs
run_ok $TEST_NAME cylc validate "$DIFF_SUITE_NAME"
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-validate-same
run_ok $TEST_NAME cylc validate "$SAME_SUITE_NAME"
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-validate-new
run_ok $TEST_NAME cylc validate "$CONTROL_SUITE_NAME"
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-bad-suites-number-1
run_fail $TEST_NAME cylc graph-diff "$DIFF_SUITE_NAME"
cmp_ok "$TEST_NAME.stdout" </dev/null
cmp_ok "$TEST_NAME.stderr" <<'__ERR__'
Usage: cylc graph-diff [OPTIONS] SUITE1 SUITE2 -- [GRAPH_OPTIONS_ARGS]

Difference 'cylc graph --reference' output for SUITE1 and SUITE2.

OPTIONS: Use '-g' to launch a graphical diff utility.
         Use '--diff-cmd=MY_DIFF_CMD' to use a custom diff tool.

SUITE1, SUITE2: Suite names to compare.
GRAPH_OPTIONS_ARGS: Options and arguments passed directly to cylc graph.
__ERR__
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-bad-suites-number-3
run_fail $TEST_NAME cylc graph-diff "$DIFF_SUITE_NAME" "$CONTROL_SUITE_NAME" \
    "$SAME_SUITE_NAME"
cmp_ok "$TEST_NAME.stdout" </dev/null
cmp_ok "$TEST_NAME.stderr" <<'__ERR__'
Usage: cylc graph-diff [OPTIONS] SUITE1 SUITE2 -- [GRAPH_OPTIONS_ARGS]

Difference 'cylc graph --reference' output for SUITE1 and SUITE2.

OPTIONS: Use '-g' to launch a graphical diff utility.
         Use '--diff-cmd=MY_DIFF_CMD' to use a custom diff tool.

SUITE1, SUITE2: Suite names to compare.
GRAPH_OPTIONS_ARGS: Options and arguments passed directly to cylc graph.
__ERR__
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-bad-suite-name
run_fail $TEST_NAME cylc graph-diff "$DIFF_SUITE_NAME" "$CONTROL_SUITE_NAME.bad"
cmp_ok "$TEST_NAME.stdout" </dev/null
cmp_ok "$TEST_NAME.stderr" <<__ERR__
Suite not found: $CONTROL_SUITE_NAME.bad
__ERR__
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-deps-fail
run_fail $TEST_NAME cylc graph-diff "$DIFF_SUITE_NAME" "$CONTROL_SUITE_NAME"
sed -i "/\.graph\.ref\./d" "$TEST_NAME.stdout"
cmp_ok "$TEST_NAME.stdout" <<'__OUT__'
@@ -1,10 +1,10 @@
-edge "bar.20140808T0000Z" "baz.20140808T0000Z" solid
-edge "bar.20140809T0000Z" "baz.20140809T0000Z" solid
-edge "bar.20140810T0000Z" "baz.20140810T0000Z" solid
 edge "cold_foo.20140808T0000Z" "foo.20140808T0000Z" solid
 edge "foo.20140808T0000Z" "bar.20140808T0000Z" solid
+edge "foo.20140808T0000Z" "baz.20140808T0000Z" solid
 edge "foo.20140809T0000Z" "bar.20140809T0000Z" solid
+edge "foo.20140809T0000Z" "baz.20140809T0000Z" solid
 edge "foo.20140810T0000Z" "bar.20140810T0000Z" solid
+edge "foo.20140810T0000Z" "baz.20140810T0000Z" solid
 graph
 node "bar.20140808T0000Z" "bar\n20140808T0000Z" unfilled box black
 node "bar.20140809T0000Z" "bar\n20140809T0000Z" unfilled box black
__OUT__
cmp_ok "$TEST_NAME.stderr" </dev/null
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-deps-ok
run_ok $TEST_NAME cylc graph-diff "$SAME_SUITE_NAME" "$CONTROL_SUITE_NAME"
cmp_ok "$TEST_NAME.stdout" </dev/null
cmp_ok "$TEST_NAME.stderr" </dev/null
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-ns
run_fail $TEST_NAME cylc graph-diff "$DIFF_SUITE_NAME" "$CONTROL_SUITE_NAME" -- --namespaces
sed -i "/\.graph\.ref\./d" "$TEST_NAME.stdout"
cmp_ok "$TEST_NAME.stdout" <<'__OUT__'
@@ -1,7 +1,7 @@
-edge FOO bar solid
-edge FOO baz solid
 edge FOO foo solid
 edge root FOO solid
+edge root bar solid
+edge root baz solid
 edge root cold_foo solid
 graph
 node FOO FOO filled box royalblue
__OUT__
cmp_ok "$TEST_NAME.stderr" </dev/null
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-custom-diff
run_ok $TEST_NAME cylc graph-diff --diff-cmd=cat "$DIFF_SUITE_NAME" "$CONTROL_SUITE_NAME"
cmp_ok "$TEST_NAME.stdout" <<'__OUT__'
edge "bar.20140808T0000Z" "baz.20140808T0000Z" solid
edge "bar.20140809T0000Z" "baz.20140809T0000Z" solid
edge "bar.20140810T0000Z" "baz.20140810T0000Z" solid
edge "cold_foo.20140808T0000Z" "foo.20140808T0000Z" solid
edge "foo.20140808T0000Z" "bar.20140808T0000Z" solid
edge "foo.20140809T0000Z" "bar.20140809T0000Z" solid
edge "foo.20140810T0000Z" "bar.20140810T0000Z" solid
graph
node "bar.20140808T0000Z" "bar\n20140808T0000Z" unfilled box black
node "bar.20140809T0000Z" "bar\n20140809T0000Z" unfilled box black
node "bar.20140810T0000Z" "bar\n20140810T0000Z" unfilled box black
node "baz.20140808T0000Z" "baz\n20140808T0000Z" unfilled box black
node "baz.20140809T0000Z" "baz\n20140809T0000Z" unfilled box black
node "baz.20140810T0000Z" "baz\n20140810T0000Z" unfilled box black
node "cold_foo.20140808T0000Z" "cold_foo\n20140808T0000Z" unfilled box black
node "foo.20140808T0000Z" "foo\n20140808T0000Z" unfilled box black
node "foo.20140809T0000Z" "foo\n20140809T0000Z" unfilled box black
node "foo.20140810T0000Z" "foo\n20140810T0000Z" unfilled box black
stop
edge "cold_foo.20140808T0000Z" "foo.20140808T0000Z" solid
edge "foo.20140808T0000Z" "bar.20140808T0000Z" solid
edge "foo.20140808T0000Z" "baz.20140808T0000Z" solid
edge "foo.20140809T0000Z" "bar.20140809T0000Z" solid
edge "foo.20140809T0000Z" "baz.20140809T0000Z" solid
edge "foo.20140810T0000Z" "bar.20140810T0000Z" solid
edge "foo.20140810T0000Z" "baz.20140810T0000Z" solid
graph
node "bar.20140808T0000Z" "bar\n20140808T0000Z" unfilled box black
node "bar.20140809T0000Z" "bar\n20140809T0000Z" unfilled box black
node "bar.20140810T0000Z" "bar\n20140810T0000Z" unfilled box black
node "baz.20140808T0000Z" "baz\n20140808T0000Z" unfilled box black
node "baz.20140809T0000Z" "baz\n20140809T0000Z" unfilled box black
node "baz.20140810T0000Z" "baz\n20140810T0000Z" unfilled box black
node "cold_foo.20140808T0000Z" "cold_foo\n20140808T0000Z" unfilled box black
node "foo.20140808T0000Z" "foo\n20140808T0000Z" unfilled box black
node "foo.20140809T0000Z" "foo\n20140809T0000Z" unfilled box black
node "foo.20140810T0000Z" "foo\n20140810T0000Z" unfilled box black
stop
__OUT__
cmp_ok "$TEST_NAME.stderr" </dev/null
#-------------------------------------------------------------------------------
purge_suite $DIFF_SUITE_NAME
purge_suite $SAME_SUITE_NAME
purge_suite $CONTROL_SUITE_NAME
