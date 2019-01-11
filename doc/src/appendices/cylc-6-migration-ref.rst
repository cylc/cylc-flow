.. _cylc-6-migration:

Cylc 6 Migration Reference
==========================

Cylc 6 introduced new date-time-related syntax for the suite.rc file. In
some places, this is quite radically different from the earlier syntax.


.. _cylc-6-migration-timeout-delays:

Timeouts and Delays
-------------------

Timeouts and delays such as ``[cylc][[events]]timeout`` or
``[runtime][[my_task]][[[job]]]execution retry delays`` were written in
a purely numeric form before cylc 6, in seconds, minutes (most common), or
hours, depending on the setting.

They are now written in an ISO 8601 duration form, which has the benefit
that the units are user-selectable (use 1 day instead of 1440 minutes)
and explicit.

Nearly all timeouts and delays in cylc were in minutes, except for:

.. code-block:: none

   [runtime][[my_task]][[[suite state polling]]]interval

.. code-block:: none

   [runtime][[my_task]][[[simulation mode]]]run time range

which were in seconds, and

.. code-block:: none

   [scheduling]runahead limit

which was in hours (this is a special case discussed below
in :ref:`cylc-6-migration-runahead-limit`).

See :ref:`Table X <cylc-6-migration-timeout-delays-table>`.

.. _cylc-6-migration-timeout-delays-table:

.. table:: Timeout/Delay Syntax Change Examples

   =========================================================  ===============  ===============
   Setting                                                    Pre-Cylc-6       Cylc-6+
   =========================================================  ===============  ===============
   ``[cylc][[events]]timeout``                                180              PT3H
   ``[runtime][[my_task]][[[job]]]execution retry delays``    2*30, 360, 1440  2*PT30M, PT6H, P1D
   ``[runtime][[my_task]][[[suite state polling]]]interval``  2                PT2S
   =========================================================  ===============  ===============


.. _cylc-6-migration-runahead-limit:

Runahead Limit
--------------

See :ref:`runahead limit`.

The ``[scheduling]runahead limit`` setting was written as a number of
hours in pre-cylc-6 suites. This is now in ISO 8601 format for date-time
cycling suites, so ``[scheduling]runahead limit=36`` would be written
``[scheduling]runahead limit=PT36H``.

There is a new preferred alternative to ``runahead limit``,
``[scheduling]max active cycle points``. This allows the user to
configure how many cycle points can run at once (default ``3``). See
:ref:`max active cycle points`.


.. _cylc-6-migration-cycle-point:

Cycle Time/Cycle Point
----------------------

See :ref:`initial cycle point`.

The following suite.rc settings have changed name
(:ref:`Table X <cylc-6-migration-cycle-point-time-table>`):

.. _cylc-6-migration-cycle-point-time-table:

.. table:: Cycle Point Renaming

   =======================================  ==================================
   Pre-Cylc-6                               Cylc-6+
   =======================================  ==================================
   ``[scheduling]initial cycle time``       ``[scheduling]initial cycle point``
   ``[scheduling]final cycle time``         ``[scheduling]final cycle point``
   ``[visualization]initial cycle time``    ``[visualization]initial cycle point``
   ``[visualization]final cycle time``      ``[visualization]final cycle point``
   =======================================  ==================================


This change is to reflect the fact that cycling in cylc 6+ can now be over
e.g. integers instead of being purely based on date-time.

Date-times written in ``initial cycle time`` and
``final cycle time`` were in a cylc-specific 10-digit (or less)
``CCYYMMDDhh`` format, such as ``2014021400`` for 00:00 on
the 14th of February 2014.

Date-times are now required to be ISO 8601 compatible. This can be achieved
easily enough by inserting a ``T`` between the day and the hour digits.

.. _cylc-6-migration-cycle-point-syntax-table:

.. table:: Cycle Point Syntax Example

   ==================================  ===============  ===============
   Setting                             Pre-Cylc-6       Cylc-6+
   ==================================  ===============  ===============
   ``[scheduling]initial cycle time``  2014021400       20140214T00
   ==================================  ===============  ===============


.. _cylc-6-migration-cycling:

Cycling
-------

Special *start-up* and *cold-start* tasks have been removed from cylc 6.
Instead, use the initial/run-once notation as detailed
in :ref:`initial-non-repeating-r1-tasks` and :ref:`AdvancedStartingUp`.

*Repeating asynchronous tasks* have also been removed because non date-time
workflows can now be handled more easily with integer cycling. See for instance
the satellite data processing example documented in :ref:`IntegerCycling`.

For repeating tasks with hour-based cycling the syntax has only minor changes:

Pre-cylc-6:

.. code-block:: cylc

   [scheduling]
       # ...
       [[dependencies]]
           [[[0,12]]]
               graph = foo[T-12] => foo & bar => baz

Cylc-6+:

.. code-block:: cylc

   [scheduling]
       # ...
       [[dependencies]]
           [[[T00,T12]]]
               graph = foo[-PT12H] => foo & bar => baz


Hour-based cycling section names are easy enough to convert, as seen in
:ref:`Table X <cylc-6-migration-cycling-hours-table>`.

.. _cylc-6-migration-cycling-hours-table:

.. table:: Hourly Cycling Sections

   ========================================  ==================================
   Pre-Cylc-6                                Cylc-6+
   ========================================  ==================================
   ``[scheduling][[dependencies]][[[0]]]``   ``[scheduling][[dependencies]][[[T00]]]``
   ``[scheduling][[dependencies]][[[6]]]``   ``[scheduling][[dependencies]][[[T06]]]``
   ``[scheduling][[dependencies]][[[12]]]``  ``[scheduling][[dependencies]][[[T12]]]``
   ``[scheduling][[dependencies]][[[18]]]``  ``[scheduling][[dependencies]][[[T18]]]``
   ========================================  ==================================


The graph text in hour-based cycling is also easy to convert, as seen in
:ref:`Table X <cylc-6-migration-cycling-hours-offset-table>`.

.. _cylc-6-migration-cycling-hours-offset-table:

.. table:: Hourly Cycling Offsets

   =================  =============================================
   Pre-Cylc-6         Cylc-6+
   =================  =============================================
   ``my_task[T-6]``   ``my_task[-PT6H]``
   ``my_task[T-12]``  ``my_task[-PT12H]``
   ``my_task[T-24]``  ``my_task[-PT24H]`` or even ``my_task[-P1D]``
   =================  =============================================


.. _cylc-6-migration-implicit-cycling:

No Implicit Creation of Tasks by Offset Triggers
------------------------------------------------

Prior to cylc-6 intercycle offset triggers implicitly created task instances at
the offset cycle points. For example, this pre cylc-6 suite automatically
creates instances of task ``foo`` at the offset hours
``3,9,15,21`` each day, for task ``bar`` to trigger off at ``0,6,12,18``:

.. code-block:: cylc

   # Pre cylc-6 implicit cycling.
   [scheduling]
      initial cycle time = 2014080800
      [[dependencies]]
         [[[00,06,12,18]]]
            # This creates foo instances at 03,09,15,21:
            graph = foo[T-3] => bar

Here's the direct translation to cylc-6+ format:

.. code-block:: cylc

   # In cylc-6+ this suite will stall.
   [scheduling]
      initial cycle point = 20140808T00
      [[dependencies]]
         [[[T00,T06,T12,T18]]]
            # This does NOT create foo instances at 03,09,15,21:
            graph = foo[-PT3H] => bar


This suite fails validation with
``ERROR: No cycling sequences defined for foo``,
and at runtime it would stall with ``bar`` instances waiting on
non-existent offset ``foo`` instances (note that these
appear as ghost nodes in graph visualisations).

To fix this, explicitly define the cycling of with an offset cycling sequence
``foo``:

.. code-block:: cylc

   # Cylc-6+ requires explicit task instance creation.
   [scheduling]
      initial cycle point = 20140808T00
      [[dependencies]]
         [[[T03,T09,T15,T21]]]
            graph = foo
         [[[T00,T06,T12,T18]]]
            graph = foo[-PT3H] => bar

Implicit task creation by offset triggers is no longer allowed because it is
error prone: a mistaken task cycle point offset should cause a failure
rather than automatically creating task instances on the wrong cycling
sequence.
