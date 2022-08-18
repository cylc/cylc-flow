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

#------------------------------------------------------------------------------
# Test rsync of workflow installation
. "$(dirname "$0")/test_header"
if ! command -v 'tree' >'/dev/null'; then
    skip_all '"tree" command not available'
fi
set_test_number 9

# Need to override any symlink dirs set in global.cylc:
create_test_global_config "" "
[install]
    [[symlink dirs]]
        [[[localhost]]]
            run =
            log =
            work =
            share =
            share/cycle =
"

# Test cylc install copies files to run dir successfully.
TEST_NAME="${TEST_NAME_BASE}-basic"
make_rnd_workflow
pushd "${RND_WORKFLOW_SOURCE}" || exit 1
mkdir .git .svn dir1 dir2
touch .git/file1 .svn/file1 dir1/file1 dir2/file1 file1 file2
run_ok "${TEST_NAME}" cylc install --no-run-name

# If rose-cylc plugin is installed add install files to tree.
export ROSE_FILES=''

tree -a -v -I '*.log|03-file-transfer*' --charset=ascii --noreport "${RND_WORKFLOW_RUNDIR}/" > 'basic-tree.out'

cmp_ok 'basic-tree.out'  <<__OUT__
${RND_WORKFLOW_RUNDIR}/
|-- _cylc-install
|   \`-- source -> ${RND_WORKFLOW_SOURCE}
|-- dir1
|   \`-- file1
|-- dir2
|   \`-- file1
|-- file1
|-- file2
|-- flow.cylc
\`-- log
    \`-- install
__OUT__

contains_ok "${TEST_NAME}.stdout" <<__OUT__
INSTALLED $RND_WORKFLOW_NAME from ${RND_WORKFLOW_SOURCE}
__OUT__
popd || exit 1
purge_rnd_workflow

# Test cylc install copies files to run dir successfully, exluding files from
# .cylcignore file.
# Should work if we run "cylc install" from source dir or not (see GH #5066)
for RUN_IN_SRC_DIR in true false; do
    TEST_NAME="${TEST_NAME_BASE}-cylcignore-${RUN_IN_SRC_DIR}"
    make_rnd_workflow
    pushd "${RND_WORKFLOW_SOURCE}" || exit 1
    mkdir .git .svn dir1 dir2 extradir1 extradir2
    touch .git/file1 .svn/file1 dir1/file1 dir2/file1 extradir1/file1 extradir2/file1 file1 file2 .cylcignore
    cat > .cylcignore <<__END__
dir*
extradir*
file2
__END__

    if ${RUN_IN_SRC_DIR}; then
        run_ok "${TEST_NAME}" cylc install --no-run-name
        CWD="${PWD}"
    else
        DTMP=$(mktemp -d)
        pushd "${DTMP}" || exit 1
        run_ok "${TEST_NAME}" cylc install --no-run-name "${RND_WORKFLOW_SOURCE}"
        CWD="${PWD}"
        popd || exit 1
    fi

    OUT="cylc-ignore-tree-${RUN_IN_SRC_DIR}.out"
    tree -a -v -I '*.log|03-file-transfer*' --charset=ascii --noreport "${RND_WORKFLOW_RUNDIR}/" > "$OUT"

    cmp_ok "$OUT"  <<__OUT__
${RND_WORKFLOW_RUNDIR}/
|-- _cylc-install
|   \`-- source -> ${RND_WORKFLOW_SOURCE}
|-- file1
|-- flow.cylc
\`-- log
    \`-- install
__OUT__

    contains_ok "${CWD}/${TEST_NAME}.stdout" <<__OUT__
INSTALLED $RND_WORKFLOW_NAME from ${RND_WORKFLOW_SOURCE}
__OUT__

    popd || exit 1
    purge_rnd_workflow
done
