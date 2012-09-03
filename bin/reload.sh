#!/bin/bash

#C: THIS FILE IS PART OF THE CYLC FORECAST SUITE METASCHEDULER.
#C: Copyright (C) 2008-2012 Hilary Oliver, NIWA
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

set -e

# Shutdown, wait, restart. Use to reload suite changes without having to 
# wait around for currently running tasks to finish prior to a manual
# restart. Be aware that suite stdout and stderr will be reattached to
# this process on the restart.

# AWAITING INCORPORATION INTO THE MAIN CYLC INTERFACE, IF USEFUL.

# NOTE: NOW WE CAN ACTUALLY RELOAD THE SUITE DEFINITION AT RUN TIME.

SUITE=$1
CYLC=$(dirname $0)/cylc

$CYLC shutdown -f $SUITE

echo "Waiting for $SUITE to shut down"
echo -n "."

while $CYLC ping $SUITE; do
    sleep 1
    echo -n "."
done
echo

echo "Restarting $SUITE"
$CYLC restart $SUITE
