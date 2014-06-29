#!/bin/bash
#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 Hilary Oliver, NIWA
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
#C: Test restarting for suites that have bad state dump files.
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 15
#-------------------------------------------------------------------------------
install_suite $TEST_NAME_BASE bad-state
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-bad-state-setup
cylc run --no-detach $SUITE_NAME || exit 1
SUITE_RUN_DIR=$(cylc get-global-config --print-run-dir)/$SUITE_NAME
STATE_FILE=$(cylc get-global-config --print-run-dir)/$SUITE_NAME/state/state
cp $STATE_FILE state.orig
SUITE_TIMEOUT=60
export SUITE_NAME SUITE_TIMEOUT
#-------------------------------------------------------------------------------
rm $STATE_FILE
TEST_NAME=$TEST_NAME_BASE-bad-state-gone
cylc restart $SUITE_NAME
START_TIME=$(date +%s)
export START_TIME
run_ok $TEST_NAME bash <<'__SCRIPT__'
while [[ -e $HOME/.cylc/ports/$SUITE_NAME ]]; do
    if [[ $(date +%s) > $(( START_TIME + SUITE_TIMEOUT )) ]]; then
        echo "[ERROR] Suite Timeout - shutting down..." >&2
        cylc shutdown --now --kill $SUITE_NAME &
        exit 1
    fi
    sleep 1
done
__SCRIPT__
grep_ok 'state dump file not found:' "$SUITE_RUN_DIR/log/suite/err"
#-------------------------------------------------------------------------------
echo "" >$STATE_FILE
TEST_NAME=$TEST_NAME_BASE-bad-state-empty
cylc restart $SUITE_NAME
START_TIME=$(date +%s)
export START_TIME
run_ok $TEST_NAME bash <<'__SCRIPT__'
while [[ -e $HOME/.cylc/ports/$SUITE_NAME ]]; do
    if [[ $(date +%s) > $(( START_TIME + SUITE_TIMEOUT )) ]]; then
        echo "[ERROR] Suite Timeout - shutting down..." >&2
        cylc shutdown --now --kill $SUITE_NAME &
        exit 1
    fi
    sleep 1
done
__SCRIPT__
grep_ok 'ERROR, incomplete suite state dump' "$SUITE_RUN_DIR/log/suite/err"
#-------------------------------------------------------------------------------
head -2 state.orig >$STATE_FILE
TEST_NAME=$TEST_NAME_BASE-bad-state-only-header
cylc restart $SUITE_NAME
START_TIME=$(date +%s)
export START_TIME
run_ok $TEST_NAME bash <<'__SCRIPT__'
while [[ -e $HOME/.cylc/ports/$SUITE_NAME ]]; do
    if [[ $(date +%s) > $(( START_TIME + SUITE_TIMEOUT )) ]]; then
        echo "[ERROR] Suite Timeout - shutting down..." >&2
        cylc shutdown --now --kill $SUITE_NAME &
        exit 1
    fi
    sleep 1
done
__SCRIPT__
grep_ok 'ERROR, incomplete suite state dump' "$SUITE_RUN_DIR/log/suite/err"
#-------------------------------------------------------------------------------
sed "s/status=[^,][^,]*, /status=quo, /g" state.orig >$STATE_FILE
TEST_NAME=$TEST_NAME_BASE-bad-state-status-wrong
cylc restart $SUITE_NAME
START_TIME=$(date +%s)
export START_TIME
run_ok $TEST_NAME bash <<'__SCRIPT__'
while [[ -e $HOME/.cylc/ports/$SUITE_NAME ]]; do
    if [[ $(date +%s) > $(( START_TIME + SUITE_TIMEOUT )) ]]; then
        echo "[ERROR] Suite Timeout - shutting down..." >&2
        cylc shutdown --now --kill $SUITE_NAME &
        exit 1
    fi
    sleep 1
done
__SCRIPT__
grep_ok 'Suite shutting down.*ERROR' "$SUITE_RUN_DIR/log/suite/log"
grep_ok 'ERROR: corrupted state dump' "$SUITE_RUN_DIR/log/suite/err"
#-------------------------------------------------------------------------------
sed "s/\(status=\).*/\1/g" state.orig >$STATE_FILE
TEST_NAME=$TEST_NAME_BASE-bad-state-status-gone
cylc restart $SUITE_NAME
START_TIME=$(date +%s)
export START_TIME
run_ok $TEST_NAME bash <<'__SCRIPT__'
while [[ -e $HOME/.cylc/ports/$SUITE_NAME ]]; do
    if [[ $(date +%s) > $(( START_TIME + SUITE_TIMEOUT )) ]]; then
        echo "[ERROR] Suite Timeout - shutting down..." >&2
        cylc shutdown --now --kill $SUITE_NAME &
        exit 1
    fi
    sleep 1
done
__SCRIPT__
grep_ok 'Suite shutting down.*ERROR' "$SUITE_RUN_DIR/log/suite/log"
grep_ok 'ERROR: corrupted state dump' "$SUITE_RUN_DIR/log/suite/err"
#-------------------------------------------------------------------------------
sed "s/\(status=\).*/\1/g" state.orig >$STATE_FILE
TEST_NAME=$TEST_NAME_BASE-bad-state-status-gone
cylc restart $SUITE_NAME
START_TIME=$(date +%s)
export START_TIME
run_ok $TEST_NAME bash <<'__SCRIPT__'
while [[ -e $HOME/.cylc/ports/$SUITE_NAME ]]; do
    if [[ $(date +%s) > $(( START_TIME + SUITE_TIMEOUT )) ]]; then
        echo "[ERROR] Suite Timeout - shutting down..." >&2
        cylc shutdown --now --kill $SUITE_NAME &
        exit 1
    fi
    sleep 1
done
__SCRIPT__
grep_ok 'Suite shutting down.*ERROR' "$SUITE_RUN_DIR/log/suite/log"
grep_ok 'ERROR: corrupted state dump' "$SUITE_RUN_DIR/log/suite/err"
#-------------------------------------------------------------------------------
purge_suite $SUITE_NAME
