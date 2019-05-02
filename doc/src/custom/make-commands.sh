#!/bin/bash

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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

# Create appendices/command-ref.rst for inclusion in HTML doc.

# All paths relative to 'doc/src/custom/' directory:
COMMAND_REF_FILE="$(dirname $0)/../appendices/command-ref.rst"
CYLC=$(dirname $0)/../../../bin/cylc

$(cat > "$COMMAND_REF_FILE" <<END
.. _CommandReference:

Command Reference
=================

.. _help:

Help
----

.. code-block:: none

   $("${CYLC}" --help | awk '{print "   " $0}')

Command Categories
------------------

END
)

for CAT in $($CYLC categories); do
	$(cat >> "$COMMAND_REF_FILE" <<END

.. _command-cat-${CAT}:

${CAT}
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: none

   $($CYLC $CAT --help | awk '{print "   " $0}')

END
)

done

$(cat >> "$COMMAND_REF_FILE" <<END

Commands
--------

END
)

for COM in $($CYLC commands); do
	$(cat >> "$COMMAND_REF_FILE" <<END

.. _command-${COM}:

${COM}
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: none

   $($CYLC $COM --help  | awk '{print "   " $0}')

END
)

done
