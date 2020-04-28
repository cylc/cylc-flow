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

cd "$(mktemp -d)" || exit 1

cat > suite.rc <<__EOF__
title = "gcylc task state color theme demo"
description = """Generate a lot of possible task states,
to show what they look like live in gcylc."""

[cylc]
  cycle point format = %Y-%m-%d
[scheduling]
    initial cycle point = 20120808
    final cycle point = 20120818
    [[queues]]
        # Use internal queues to see tasks in the "queued" state
        [[[fam_queue]]]
            limit = 2
            members = FAMILY
    [[graph]]
        R1 = cfoo => foo
        P1D =  """
    foo[-P1D] => foo => FAMILY
    FAMILY:finish-all => bar
    foo => bird & fish & dog
    bar => !bird & !fish"""
[runtime]
    [[root]]
        # delay all tasks slightly in the 'submitted' state
        init-script = "sleep 5"
        pre-script = "sleep \$(( RANDOM % 30 ))"
    [[FAMILY]]
    [[m1,m2,m3]]
        inherit = FAMILY
    [[m_x]]
        inherit = FAMILY
        title = "this task succeeds on the second try "
        retry delays = PT18S
        script = """
sleep 10
if [[ \$CYLC_TASK_TRY_NUMBER < 2 ]]; then
    cylc task message -p WARNING ABORTING
    exit 1
fi"""
    [[bird]]
        title = "A task that tries and fails twice"
        description = """Failed instances of this task are removed from the suite
at the end of each cycle by a suicide trigger."""
        retry delays = PT12S
        script = "sleep 10; exit 1"
    [[fish]]
        title = "A task that fails to submit twice"
        [[[job]]]
            batch system = fail
            submission retry delays = PT18S
    [[dog]]
        title = "A task successfully submits on the second try "
        description = """Uses a retry event handler to broadcast a new job
submission method for the retry."""
        [[[job]]]
            batch system = fail
            submission retry delays = PT18S
        [[[events]]]
            submission retry handler = change-my-job-sub-method.sh
[visualization]
    use node color for labels = True
    [[node attributes]]
        FAMILY = "style=filled", "color=#0000aa", "fillcolor=red"
        foo = "style=unfilled", "color=blue"
__EOF__

DEST=groups
rm -rf $DEST
rm -rf ~/cylc-run/$DEST

SKIP=4
for GROUP in nwp tst opr; do
  for N in 1 2 3 4; do
    if (( SKIP == N )); then
      SKIP=$(( SKIP - 1))
      break
    fi
    SUITE=${GROUP}-$N
    mkdir -p $DEST/$SUITE
    cp -r suite.rc $DEST/$SUITE
    perl -pi -e "s/\[cylc\]/title = $GROUP suite $N\ngroup = $GROUP\n[cylc]/" $DEST/$SUITE/suite.rc
    cylc reg $DEST/$SUITE $DEST/$SUITE
    cylc run $DEST/$SUITE > /dev/null &
  done
done

cylc scan -n groups
