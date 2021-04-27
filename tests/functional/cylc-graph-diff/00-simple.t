#!/usr/bin/env bash
# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
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
# Test cylc graph --diff for two workflows.
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 15
#-------------------------------------------------------------------------------
install_workflow "${TEST_NAME_BASE}-control" "${TEST_NAME_BASE}-control"
CONTROL_WORKFLOW_NAME="${WORKFLOW_NAME}"
install_workflow "${TEST_NAME_BASE}-diffs" "${TEST_NAME_BASE}-diffs"
DIFF_WORKFLOW_NAME="${WORKFLOW_NAME}"
install_workflow "${TEST_NAME_BASE}-same" "${TEST_NAME_BASE}-same"
SAME_WORKFLOW_NAME="${WORKFLOW_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate-diffs"
run_ok "${TEST_NAME}" cylc validate "${DIFF_WORKFLOW_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate-same"
run_ok "${TEST_NAME}" cylc validate "${SAME_WORKFLOW_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate-new"
run_ok "${TEST_NAME}" cylc validate "${CONTROL_WORKFLOW_NAME}"
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-bad-workflow-name"
run_fail "${TEST_NAME}" \
    cylc graph "${DIFF_WORKFLOW_NAME}" --diff "${CONTROL_WORKFLOW_NAME}.bad"
cmp_ok "${TEST_NAME}.stdout" </'dev/null'
cmp_ok "${TEST_NAME}.stderr" <<__ERR__
WorkflowFilesError: no flow.cylc or suite.rc in ${RUN_DIR}/${CONTROL_WORKFLOW_NAME}.bad
__ERR__
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-deps-fail"
run_fail "${TEST_NAME}" \
    cylc graph "${DIFF_WORKFLOW_NAME}" --diff "${CONTROL_WORKFLOW_NAME}"
sed -i "/\.graph\.ref\./d" "${TEST_NAME}.stdout"
cmp_ok "${TEST_NAME}.stdout" <<__OUT__
--- ${DIFF_WORKFLOW_NAME}
+++ ${CONTROL_WORKFLOW_NAME}
@@ -1,10 +1,10 @@
-edge "bar.20140808T0000Z" "baz.20140808T0000Z"
-edge "bar.20140809T0000Z" "baz.20140809T0000Z"
-edge "bar.20140810T0000Z" "baz.20140810T0000Z"
 edge "cold_foo.20140808T0000Z" "foo.20140808T0000Z"
 edge "foo.20140808T0000Z" "bar.20140808T0000Z"
+edge "foo.20140808T0000Z" "baz.20140808T0000Z"
 edge "foo.20140809T0000Z" "bar.20140809T0000Z"
+edge "foo.20140809T0000Z" "baz.20140809T0000Z"
 edge "foo.20140810T0000Z" "bar.20140810T0000Z"
+edge "foo.20140810T0000Z" "baz.20140810T0000Z"
 graph
 node "bar.20140808T0000Z" "bar\n20140808T0000Z"
 node "bar.20140809T0000Z" "bar\n20140809T0000Z"
__OUT__
cmp_ok "${TEST_NAME}.stderr" <'/dev/null'
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-deps-ok"
run_ok "${TEST_NAME}" \
    cylc graph "${SAME_WORKFLOW_NAME}" --diff "${CONTROL_WORKFLOW_NAME}"
cmp_ok "${TEST_NAME}.stdout" <'/dev/null'
cmp_ok "${TEST_NAME}.stderr" <'/dev/null'
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-ns"
run_fail "${TEST_NAME}" \
    cylc graph "${DIFF_WORKFLOW_NAME}" --diff "${CONTROL_WORKFLOW_NAME}" --namespaces
sed -i "/\.graph\.ref\./d" "${TEST_NAME}.stdout"
cmp_ok "${TEST_NAME}.stdout" <<__OUT__
--- ${DIFF_WORKFLOW_NAME}
+++ ${CONTROL_WORKFLOW_NAME}
@@ -1,7 +1,7 @@
-edge FOO bar
-edge FOO baz
 edge FOO foo
 edge root FOO
+edge root bar
+edge root baz
 edge root cold_foo
 graph
 node FOO FOO
__OUT__
cmp_ok "${TEST_NAME}.stderr" <'/dev/null'
#-------------------------------------------------------------------------------
purge "${DIFF_WORKFLOW_NAME}"
purge "${SAME_WORKFLOW_NAME}"
purge "${CONTROL_WORKFLOW_NAME}"
