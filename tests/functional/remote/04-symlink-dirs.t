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
# Checks configured symlinks are created for run, work, share, share/cycle, log
# # directories on localhost and the remote platform.
export REQUIRE_PLATFORM='loc:remote comms:tcp fs:indep'
. "$(dirname "$0")/test_header"

if [[ -z ${TMPDIR:-} || -z ${USER:-} || $TMPDIR/$USER == "$HOME" ]]; then
    skip_all '"TMPDIR" or "USER" not defined or "TMPDIR"/"USER" is "HOME"'
fi

set_test_number 14

create_test_global_config "" "
[install]
    [[symlink dirs]]
        [[[localhost]]]
            run = \$TMPDIR/\$USER/cylctb_tmp_run_dir
            share = \$TMPDIR/\$USER
            log = \$TMPDIR/\$USER
            log/job = \$TMPDIR/\$USER/cylctb_tmp_log_job_dir
            share/cycle = \$TMPDIR/\$USER/cylctb_tmp_share_dir
            work = \$TMPDIR/\$USER
        [[[$CYLC_TEST_INSTALL_TARGET]]]
            run = \$TMPDIR/\$USER/test_cylc_symlink/ctb_tmp_run_dir
            share = \$TMPDIR/\$USER/test_cylc_symlink/
            log = \$TMPDIR/\$USER/test_cylc_symlink/
            log/job = \$TMPDIR/\$USER/cylctb_tmp_log_job_dir
            share/cycle = \$TMPDIR/\$USER/test_cylc_symlink/ctb_tmp_share_dir
            work = \$TMPDIR/\$USER/test_cylc_symlink/
"

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}" \
    -s "CYLC_TEST_PLATFORM='${CYLC_TEST_PLATFORM}'"
workflow_run_ok "${TEST_NAME_BASE}-run-ok" cylc play "${WORKFLOW_NAME}" \
    -s "CYLC_TEST_PLATFORM='${CYLC_TEST_PLATFORM}'" --debug
poll_grep_workflow_log 'remote file install complete'
TEST_SYM="${TEST_NAME_BASE}-run-symlink-exists-ok"
if [[ $(readlink "$HOME/cylc-run/${WORKFLOW_NAME}") == \
    "$TMPDIR/$USER/cylctb_tmp_run_dir/cylc-run/${WORKFLOW_NAME}" ]]; then
        ok "$TEST_SYM.localhost"
else
    fail "$TEST_SYM.localhost"
fi

TEST_SYM="${TEST_NAME_BASE}-share/cycle-symlink-exists-ok"
if [[ $(readlink "$HOME/cylc-run/${WORKFLOW_NAME}/share/cycle") == \
"$TMPDIR/$USER/cylctb_tmp_share_dir/cylc-run/${WORKFLOW_NAME}/share/cycle" ]]; then
    ok "$TEST_SYM.localhost"
else
    fail "$TEST_SYM.localhost"
fi

TEST_SYM="${TEST_NAME_BASE}-log/job-symlink-exists-ok"
if [[ $(readlink "$HOME/cylc-run/${WORKFLOW_NAME}/log/job") == \
"$TMPDIR/$USER/cylctb_tmp_log_job_dir/cylc-run/${WORKFLOW_NAME}/log/job" ]]; then
    ok "$TEST_SYM.localhost"
else
    fail "$TEST_SYM.localhost"
fi

for DIR in 'work' 'share' 'log'; do
    TEST_SYM="${TEST_NAME_BASE}-${DIR}-symlink-exists-ok"
    if [[ $(readlink "$HOME/cylc-run/${WORKFLOW_NAME}/${DIR}") == \
   "$TMPDIR/$USER/cylc-run/${WORKFLOW_NAME}/${DIR}" ]]; then
        ok "$TEST_SYM.localhost"
    else
        fail "$TEST_SYM.localhost"
    fi
done

SSH="$(cylc config -d -i "[platforms][$CYLC_TEST_PLATFORM]ssh command")"

# shellcheck disable=SC2016
LINK="$(${SSH} "${CYLC_TEST_HOST}" 'readlink "$HOME/cylc-run/'"$WORKFLOW_NAME"'"')"
if [[ "$LINK" == *"/test_cylc_symlink/ctb_tmp_run_dir/cylc-run/${WORKFLOW_NAME}" ]]; then
    ok "${TEST_NAME_BASE}-run-symlink-exists-ok.remotehost"
else
    fail "${TEST_NAME_BASE}-run-symlink-exists-ok.remotehost"
fi

# shellcheck disable=SC2016
LINK="$(${SSH} "${CYLC_TEST_HOST}" 'readlink "$HOME/cylc-run/'"$WORKFLOW_NAME"/share/cycle'"')"
if [[ "$LINK" == *"/test_cylc_symlink/ctb_tmp_share_dir/cylc-run/${WORKFLOW_NAME}/share/cycle" ]]; then
    ok "${TEST_NAME_BASE}-share/cycle-symlink-exists-ok.remotehost"
else
    fail "${TEST_NAME_BASE}-share/cycle-symlink-exists-ok.remotehost"
fi

# shellcheck disable=SC2016
LINK="$(${SSH} "${CYLC_TEST_HOST}" 'readlink "$HOME/cylc-run/'"$WORKFLOW_NAME"/log/job'"')"
if [[ "$LINK" == *"/cylctb_tmp_log_job_dir/cylc-run/${WORKFLOW_NAME}/log/job" ]]; then
    ok "${TEST_NAME_BASE}-log/job-symlink-exists-ok.remotehost"
else
    fail "${TEST_NAME_BASE}-log/job-symlink-exists-ok.remotehost"
fi

for DIR in 'work' 'share' 'log'; do
# shellcheck disable=SC2016
    LINK="$(${SSH} "${CYLC_TEST_HOST}" 'readlink "$HOME/cylc-run/'"$WORKFLOW_NAME"/$DIR'"')"
    if [[ "$LINK" == *"/test_cylc_symlink/cylc-run/${WORKFLOW_NAME}/${DIR}" ]]; then
        ok "${TEST_NAME_BASE}-${DIR}-symlink-exists-ok.remotehost"
    else
        fail "${TEST_NAME_BASE}-${DIR}-symlink-exists-ok.remotehost"
    fi
done

# clean up remote
${SSH} "${CYLC_TEST_HOST}" rm -rf "${TMPDIR}/${USER}/test_cylc_symlink/"
purge
exit
