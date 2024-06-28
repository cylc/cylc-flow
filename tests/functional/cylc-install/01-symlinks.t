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
# Test workflow installation symlinking localhost

. "$(dirname "$0")/test_header"

if [[ -z ${TMPDIR:-} || -z ${USER:-} || $TMPDIR/$USER == "$HOME" ]]; then
    skip_all '"TMPDIR" or "USER" not defined or "TMPDIR"/"USER" is "HOME"'
fi

set_test_number 32

create_test_global_config "" "
[install]
[[symlink dirs]]
    [[[localhost]]]
        run = \$TMPDIR/\$USER/test_cylc_symlink/cylctb_tmp_run_dir
        share = \$TMPDIR/\$USER/test_cylc_symlink/
        log = \$TMPDIR/\$USER/test_cylc_symlink/
        log/job = \$TMPDIR/\$USER/test_cylc_symlink/job_log_dir
        share/cycle = \$TMPDIR/\$USER/test_cylc_symlink/cylctb_tmp_share_dir
        work = \$TMPDIR/\$USER/test_cylc_symlink/
"

# Test "cylc install" ensure symlinks are created
TEST_NAME="${TEST_NAME_BASE}-symlinks-created"
make_rnd_workflow
run_ok "${TEST_NAME}" cylc install --workflow-name="${RND_WORKFLOW_NAME}" "${RND_WORKFLOW_SOURCE}"
contains_ok "${TEST_NAME}.stdout" <<__OUT__
INSTALLED $RND_WORKFLOW_NAME/run1 from ${RND_WORKFLOW_SOURCE}
__OUT__
WORKFLOW_RUN_DIR="$HOME/cylc-run/${RND_WORKFLOW_NAME}/run1"
TEST_SYM="${TEST_NAME_BASE}-run-glblcfg"
run_ok "${TEST_SYM}" test "$(readlink "${WORKFLOW_RUN_DIR}")" \
    = "$TMPDIR/${USER}/test_cylc_symlink/cylctb_tmp_run_dir/cylc-run/${RND_WORKFLOW_NAME}/run1"

TEST_SYM="${TEST_NAME_BASE}-share-cycle-glblcfg"
run_ok "${TEST_SYM}" test "$(readlink "${WORKFLOW_RUN_DIR}/share/cycle")" \
    = "$TMPDIR/${USER}/test_cylc_symlink/cylctb_tmp_share_dir/cylc-run/${RND_WORKFLOW_NAME}/run1/share/cycle"

TEST_SYM="${TEST_NAME_BASE}-log-job-glblcfg"
run_ok "${TEST_SYM}" test "$(readlink "${WORKFLOW_RUN_DIR}/log/job")" \
    = "$TMPDIR/${USER}/test_cylc_symlink/job_log_dir/cylc-run/${RND_WORKFLOW_NAME}/run1/log/job"

for DIR in 'work' 'share' 'log'; do
    TEST_SYM="${TEST_NAME_BASE}-${DIR}-glbcfg"
    run_ok "${TEST_SYM}" test "$(readlink "${WORKFLOW_RUN_DIR}/${DIR}")" \
   = "$TMPDIR/${USER}/test_cylc_symlink/cylc-run/${RND_WORKFLOW_NAME}/run1/${DIR}"
done
rm -rf "${TMPDIR}/${USER}/test_cylc_symlink/"
purge_rnd_workflow

# test cli --symlink-dirs overrides the glblcfg
SYMDIR=${TMPDIR}/${USER}/test_cylc_cli_symlink/

TEST_NAME="${TEST_NAME_BASE}-cli-opt-install"
make_rnd_workflow
run_ok "${TEST_NAME}" cylc install "${RND_WORKFLOW_SOURCE}" \
    --workflow-name="${RND_WORKFLOW_NAME}" \
    --symlink-dirs="run= ${SYMDIR}cylctb_tmp_run_dir, log=${SYMDIR}, share=${SYMDIR}, \
    work = ${SYMDIR}"
contains_ok "${TEST_NAME}.stdout" <<__OUT__
INSTALLED $RND_WORKFLOW_NAME/run1 from ${RND_WORKFLOW_SOURCE}
__OUT__
WORKFLOW_RUN_DIR="$HOME/cylc-run/${RND_WORKFLOW_NAME}/run1"

TEST_SYM="${TEST_NAME_BASE}-run-cli"
run_ok "$TEST_SYM" test "$(readlink "${WORKFLOW_RUN_DIR}")" \
   =  "$TMPDIR/${USER}/test_cylc_cli_symlink/cylctb_tmp_run_dir/cylc-run/${RND_WORKFLOW_NAME}/run1"


for DIR in 'work' 'share' 'log'; do
    TEST_SYM="${TEST_NAME_BASE}-${DIR}-cli"
    run_ok "$TEST_SYM" test "$(readlink "${WORKFLOW_RUN_DIR}/${DIR}")" \
   = "${TMPDIR}/${USER}/test_cylc_cli_symlink/cylc-run/${RND_WORKFLOW_NAME}/run1/${DIR}"
done

INSTALL_LOG="$(find "${WORKFLOW_RUN_DIR}/log/install" -type f -name '*.log')"

for DIR in 'work' 'share' 'log'; do
    grep_ok "${TMPDIR}/${USER}/test_cylc_cli_symlink/cylc-run/${RND_WORKFLOW_NAME}/run1/${DIR}" "${INSTALL_LOG}"
done

# test cylc play symlinks after cli opts (mapping to different directories)

pushd "${WORKFLOW_RUN_DIR}" || exit 1
cat > 'flow.cylc' << __FLOW__
[scheduling]
    [[graph]]
        R1 = foo
[runtime]
    [[foo]]
        script = true
__FLOW__

popd || exit 1

run_ok "${TEST_NAME_BASE}-play" cylc play "${RND_WORKFLOW_NAME}/runN" --debug --no-detach

# test ensure symlinks, not in cli install are not created from glbl cfg.
TEST_SYM="${TEST_NAME_BASE}-share-cycle-cli"
run_fail "$TEST_SYM" test "$(readlink "${WORKFLOW_RUN_DIR}/share/cycle")" \
= "$TMPDIR/${USER}/test_cylc_symlink/cylctb_tmp_share_dir/cylc-run/${RND_WORKFLOW_NAME}/run1/share/cycle"

rm -rf "${TMPDIR}/${USER}/test_cylc_cli_symlink/"
purge_rnd_workflow


# test no symlinks created with --symlink-dirs=""

TEST_NAME="${TEST_NAME_BASE}-no-sym-dirs-cli"
make_rnd_workflow
run_ok "${TEST_NAME}" cylc install "${RND_WORKFLOW_SOURCE}" \
    --workflow-name="${RND_WORKFLOW_NAME}" --symlink-dirs=""
contains_ok "${TEST_NAME}.stdout" <<__OUT__
INSTALLED $RND_WORKFLOW_NAME/run1 from ${RND_WORKFLOW_SOURCE}
__OUT__
WORKFLOW_RUN_DIR="$HOME/cylc-run/${RND_WORKFLOW_NAME}/run1"


TEST_SYM="${TEST_NAME}-run"
run_fail "${TEST_SYM}" test "$(readlink "${WORKFLOW_RUN_DIR}")" \
    = "$TMPDIR/${USER}/test_cylc_symlink/cylctb_tmp_run_dir/cylc-run/${RND_WORKFLOW_NAME}/run1"

TEST_SYM="${TEST_NAME}-share-cycle"
run_fail "${TEST_SYM}" test "$(readlink "${WORKFLOW_RUN_DIR}/share/cycle")" \
    = "$TMPDIR/${USER}/test_cylc_symlink/cylctb_tmp_share_dir/cylc-run/${RND_WORKFLOW_NAME}/run1/share/cycle"

TEST_SYM="${TEST_NAME}-log-job"
run_fail "${TEST_SYM}" test "$(readlink "${WORKFLOW_RUN_DIR}/log/job")" \
    = "$TMPDIR/${USER}/test_cylc_symlink/job_log_dir/cylc-run/${RND_WORKFLOW_NAME}/run1/log/job"

for DIR in 'work' 'share' 'log'; do
    TEST_SYM="${TEST_NAME}-${DIR}"
    run_fail "${TEST_SYM}" test "$(readlink "${WORKFLOW_RUN_DIR}/${DIR}")" \
   = "$TMPDIR/${USER}/test_cylc_symlink/cylc-run/${RND_WORKFLOW_NAME}/run1/${DIR}"
done

pushd "${WORKFLOW_RUN_DIR}" || exit 1
cat > 'flow.cylc' << __FLOW__
[scheduling]
    [[graph]]
        R1 = foo
[runtime]
    [[foo]]
        script = true
__FLOW__

popd || exit 1

run_ok "${TEST_NAME_BASE}-play" cylc play "${RND_WORKFLOW_NAME}/runN" --debug --no-detach
# test ensure localhost symlink dirs skipped for installed workflows.
TEST_SYM="${TEST_NAME_BASE}-installed-workflow-skips-symdirs"
run_fail "${TEST_SYM}" test "$(readlink "${WORKFLOW_RUN_DIR}")" \
    = "$TMPDIR/${USER}/test_cylc_symlink/cylctb_tmp_run_dir/cylc-run/${RND_WORKFLOW_NAME}/run1"
rm -rf "${TMPDIR}/${USER}/test_cylc_cli_symlink/"
purge_rnd_workflow


# test share and share/cycle same symlinks don't error
SYMDIR=${TMPDIR}/${USER}/test_cylc_cli_symlink/

TEST_NAME="${TEST_NAME_BASE}-share-share-cycle-same-dirs"
make_rnd_workflow
# check install runs without failure
run_ok "${TEST_NAME}" cylc install "${RND_WORKFLOW_SOURCE}" \
    --workflow-name="${RND_WORKFLOW_NAME}" \
    --symlink-dirs="share/cycle=${SYMDIR}, share=${SYMDIR}"
contains_ok "${TEST_NAME}.stdout" <<__OUT__
INSTALLED $RND_WORKFLOW_NAME/run1 from ${RND_WORKFLOW_SOURCE}
__OUT__
WORKFLOW_RUN_DIR="$HOME/cylc-run/${RND_WORKFLOW_NAME}/run1"

TEST_SYM="${TEST_NAME_BASE}-share-cli"
run_ok "$TEST_SYM" test "$(readlink "${WORKFLOW_RUN_DIR}/share")" \
   = "${TMPDIR}/${USER}/test_cylc_cli_symlink/cylc-run/${RND_WORKFLOW_NAME}/run1/share"

rm -rf "${TMPDIR}/${USER}/test_cylc_cli_symlink/"
purge_rnd_workflow
