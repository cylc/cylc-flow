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

cd "$(mktemp -d)" || exit 1

cat > flow.cylc <<__EOF__
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
        script = """
sleep 10
if [[ \$CYLC_TASK_TRY_NUMBER < 2 ]]; then
    cylc task message -p WARNING ABORTING
    exit 1
fi"""
        [[[job]]]
        execution retry delays = PT18S

    [[bird]]
        script = "sleep 10; exit 1"
        [[[job]]]
        execution retry delays = PT12S
    [[fish]]
        [[[job]]]
            batch system = fail
            submission retry delays = PT18S
    [[dog]]
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
    cp -r flow.cylc $DEST/$SUITE
    cylc reg $DEST/$SUITE $DEST/$SUITE
    cylc run $DEST/$SUITE > /dev/null &
  done
done

cylc scan -n groups
