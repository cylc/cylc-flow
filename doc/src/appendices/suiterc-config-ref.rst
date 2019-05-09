.. _SuiteRCReference:

Suite.rc Reference
==================

This appendix defines all legal suite configuration items.
Embedded Jinja2 code (see :ref:`Jinja`) must process to a valid
raw suite.rc file. See also :ref:`SuiteRCFile` for a descriptive
overview of suite.rc files, including syntax (:ref:`Syntax`).


Top Level Items
---------------

The only top level configuration items at present are the suite title
and description.


[meta]
------

Section containing metadata items for this suite. Several items
(title, description, URL) are pre-defined and are used by Cylc. Others
can be user-defined and passed to suite event handlers to be interpreted
according to your needs. For example, the value of a "suite-priority" item
could determine how an event handler responds to failure events.


[meta] ``->`` title
^^^^^^^^^^^^^^^^^^^

A single line description of the suite, can be retrieved at run time with the
``cylc show`` command.

- *type*: single line string
- *default*: (none)


[meta] ``->`` description
^^^^^^^^^^^^^^^^^^^^^^^^^

A multi-line description of the suite. It can be retrieved at run time
with the ``cylc show`` command.

- *type*: multi-line string
- *default*: (none)


.. _SuiteURL:

[meta] ``->`` URL
^^^^^^^^^^^^^^^^^

A web URL to suite documentation.  If present it can be browsed with the
``cylc doc`` command. The string
template ``%(suite_name)s`` will be replaced with the actual suite
name. See also :ref:`TaskURL`.

- *type*: string (URL)
- *default*: (none)
- *example*: ``http://my-site.com/suites/%(suite_name)s/index.html``


[meta] ``->`` group
^^^^^^^^^^^^^^^^^^^

A group name for a suite.

- *type*: single line string
- *default*: (none)


[meta] ``->`` \_\_MANY\_\_
^^^^^^^^^^^^^^^^^^^^^^^^^^

Replace ``__MANY__`` with any user-defined metadata item. These, like
title, URL, etc. can be passed to suite event handlers to be interpreted
according to your needs. For example, "suite-priority".

- *type*: String or integer
- *default*: (none)
- *example*:

   .. code-block:: cylc

      [meta]
          suite-priority = high


[cylc]
------

This section is for configuration that is not specifically task-related.


[cylc] ``->`` required run mode
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If this item is set cylc will abort if the suite is not started in the
specified mode. This can be used for demo suites that have to be
run in simulation mode, for example, because they have been taken out of
their normal operational context; or to prevent accidental submission of
expensive real tasks during suite development.

- *type*: string
- *legal values*: live, dummy, dummy-local, simulation
- *default*: None


.. _UTC-mode:

[cylc] ``->`` UTC mode
^^^^^^^^^^^^^^^^^^^^^^

Cylc runs off the suite host's system clock by default. This item allows
you to run the suite in UTC even if the system clock is set to local time.
Clock-trigger tasks will trigger when the current UTC time is equal to
their cycle point date-time plus offset; other time values used, reported, or
logged by the suite server program will usually also be in UTC. The default for
this can be set at the site level (see :ref:`SiteUTCMode`).

- *type*: boolean
- *default*: False, unless overridden at site level.


.. _cycle-point-format:

[cylc] ``->`` cycle point format
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To just alter the timezone used in the date-time cycle point format, see
:ref:`cycle-point-time-zone`. To just alter the number of expanded year digits
(for years below 0 or above 9999), see
:ref:`cycle-point-num-expanded-year-digits`.

Cylc usually uses a ``CCYYMMDDThhmmZ`` (``Z`` in the special
case of UTC) or ``CCYYMMDDThhmm+hhmm`` format (``+`` standing
for ``+`` or ``-`` here) for writing down date-time cycle
points, which follows one of the basic formats outlined in the ISO 8601
standard. For example, a cycle point on the 3rd of February 2001 at 4:50 in
the morning, UTC (+0000 timezone), would be written
``20010203T0450Z``. Similarly, for the 3rd of February 2001 at
4:50 in the morning, +1300 timezone, cylc would write
``20010203T0450+1300``.

You may use the isodatetime library's syntax to write dates and times in ISO
8601 formats - ``CC`` for century, ``YY`` for decade and
decadal year, ``+X`` for expanded year digits and their positive or
negative sign, thereafter following the ISO 8601 standard example notation
except for fractional digits, which are represented as ``,ii`` for
``hh``, ``,nn`` for ``mm``, etc. For example, to write
date-times as week dates with fractional hours, set cycle point format to
``CCYYWwwDThh,iiZ`` e.g.  ``1987W041T08,5Z`` for 08:30 UTC on
Monday on the fourth ISO week of 1987.

You can also use a subset of the strptime/strftime POSIX standard - supported
tokens are ``%F``, ``%H``, ``%M``, ``%S``,
``%Y``, ``%d``, ``%j``, ``%m``, ``%s``, ``%z``.

The ISO8601 extended date-time format can be used
(``%Y-%m-%dT%H:%M``) but
note that the "-" and ":" characters end up in job log directory paths.

.. _cycle-point-num-expanded-year-digits:

[cylc] ``->`` cycle point num expanded year digits
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

For years below 0 or above 9999, the ISO 8601 standard specifies that an
extra number of year digits and a sign should be used. This extra number needs
to be written down somewhere (here).

For example, if this extra number is set to 2, 00Z on the 1st of January in
the year 10040 will be represented as ``+0100400101T0000Z`` (2 extra
year digits used). With this number set to 3, 06Z on the 4th of May 1985 would
be written as ``+00019850504T0600Z``.

This number defaults to 0 (no sign or extra digits used).


.. _cycle-point-time-zone:

[cylc] ``->`` cycle point time zone
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you set UTC mode to True (:ref:`UTC-mode`) then this will default to
``Z``. If you use a custom cycle point format
(:ref:`cycle-point-format`), you should specify the timezone choice (or null
timezone choice) here as well.

You may set your own time zone choice here, which will be used for all
date-time cycle point dumping. Time zones should be expressed as ISO 8601 time
zone offsets from UTC, such as ``+13``, ``+1300``,
``-0500`` or ``+0645``, with ``Z`` representing the
special ``+0000`` case. Cycle points will be converted to the time
zone you give and will be represented with this string at the end.

Cycle points that are input without time zones (e.g. as an initial cycle
point
setting) will use this time zone if set. If this isn't set (and UTC mode is
also not set), then they will default to the current local time zone.

.. note::

   The ISO standard also allows writing the hour and minute separated
   by a ":" (e.g. ``+13:00``) - however, this is not recommended, given
   that the time zone is used as part of task output filenames.


[cylc] ``->`` abort if any task fails
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Cylc does not normally abort if tasks fail, but if this item is turned
on it will abort with exit status 1 if any task fails.

- *type*: boolean
- *default*: False


.. _health-check-interval:

[cylc] ``->`` health check interval
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Specify the time interval on which a running cylc suite will check that its run
directory exists and that its contact file contains the expected information.
If not, the suite will shut itself down automatically.

- *type*: ISO 8601 duration/interval representation (e.g. 
  ``PT5M``, 5 minutes (note: by contrast, ``P5M`` means 5
  months, so remember the ``T``!)).
- *default*: PT10M


.. _task-event-mail-interval:

[cylc] ``->`` task event mail interval
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Group together all the task event mail notifications into a single email within
a given interval. This is useful to prevent flooding users' mail boxes when
many task events occur within a short period of time.

- *type*: ISO 8601 duration/interval representation (e.g.
  ``PT10S``, 10 seconds, or ``PT1M``, 1 minute).
- *default*: PT5M


[cylc] ``->`` disable automatic shutdown
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This has the same effect as the ``--no-auto-shutdown`` flag for
the suite run commands: it prevents the suite server program from shutting down
normally when all tasks have finished (a suite timeout can still be used to
stop the daemon after a period of inactivity, however).  This option can
make it easier to re-trigger tasks manually near the end of a suite run,
during suite development and debugging.

- *type*: boolean
- *default*: False


[cylc] ``->`` log resolved dependencies
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If this is turned on cylc will write the resolved dependencies of each
task to the suite log as it becomes ready to run (a list of the IDs of
the tasks that actually satisfied its prerequisites at run time). Mainly
used for cylc testing and development.

- *type*: boolean
- *default*: False


[cylc] ``->`` [[parameters]]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Define parameter values here for use in expanding *parameterized tasks* -
see :ref:`Parameterized Tasks Label`.

- *type*: list of strings, or an integer range
  ``LOWER..UPPER..STEP`` (two dots, inclusive bounds, "STEP" optional)
- *default*: (none)
- *examples*:
  - ``run = control, test1, test2``
  - ``mem = 1..5``  (equivalent to ``1, 2, 3, 4, 5``).
  - ``mem = -11..-7..2``  (equivalent to ``-11, -9, -7``).


.. _RefParameterTemplates:

[cylc] ``->`` [[parameter templates]]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Parameterized task names (see previous item, and
:ref:`Parameterized Tasks Label`) are expanded, for each parameter value,
using string templates.  You can assign templates to parameter names here,
to override the default templates.

- *type*: a Python-style string template
- *default} for integer parameters* ``p``:
  ``_p%(p)0Nd``
  where ``N`` is the number of digits of the maximum integer value,
  e.g. ``foo<run>`` becomes ``foo_run3`` for ``run`` value ``3``.
- *default for non-integer parameters* ``p``:
  ``_%(p)s`` e.g. ``foo<run>`` becomes ``foo_top`` for
  ``run`` value ``top``.
- *example*: ``run = -R%(run)s`` e.g. ``foo<run>`` becomes ``foo-R3`` for
  ``run`` value ``3``.

.. note::

   The values of a parameter named ``p`` are substituted for ``%(p)s``.
   In ``_run%(run)s`` the first "run" is a string literal, and the second
   gets substituted with each value of the parameter.


.. _SuiteEventHandling:

[cylc] ``->`` [[events]]
^^^^^^^^^^^^^^^^^^^^^^^^

Cylc has internal "hooks" to which you can attach handlers that are
called by the suite server program whenever certain events occur. This section
configures suite events; see :ref:`TaskEventHandling` for
task events.

Event handler commands can send an email or an SMS, call a pager, intervene in
the operation of their own suite, or whatever.
They can be held in the suite bin directory, otherwise it is up to you
to ensure their location is in ``$PATH`` (in the shell in which
cylc runs, on the suite host). The commands should require
very little resource to run and should return quickly.

Each event handler can be specified as a list of command lines or command
line templates.

A command line template may have any or all of these patterns which will be
substituted with actual values:

- \%(event)s: event name (see below)
- \%(suite)s: suite name
- \%(suite\_url)s: suite URL
- \%(suite\_uuid)s: suite UUID string
- \%(message)s: event message, if any
- any suite [meta] item, e.g.:
  - \%(title)s: suite title
  - \%(importance)s: example custom suite metadata

Otherwise the command line will be called with the following default
arguments:

.. code-block:: none

   <suite-event-handler> %(event)s %(suite)s %(message)s

.. note::

   Substitution patterns should not be quoted in the template strings.
   This is done automatically where required.

Additional information can be passed to event handlers via
[cylc] ``->`` [[environment]].


[cylc] ``->`` [[events]] ``->`` EVENT handler
"""""""""""""""""""""""""""""""""""""""""""""

A comma-separated list of one or more event handlers to call when one of the
following EVENTs occurs:

- **startup**  - the suite has started running
- **shutdown** - the suite is shutting down
- **aborted** - the suite is shutting down due to unexpected/unrecoverable error
- **timeout**  - the suite has timed out
- **stalled** - the suite has stalled
- **inactivity** - the suite is inactive

Default values for these can be set at the site level via the siterc file
(see :ref:`SiteCylcHooks`).

Item details:

- *type*: string (event handler script name)
- *default*: None, unless defined at the site level.
- *example*: ``startup handler = my-handler.sh``


[cylc] ``->`` [[[events]]] ``->`` handlers
""""""""""""""""""""""""""""""""""""""""""

Specify the general event handlers as a list of command lines or command line
templates.

- *type*: Comma-separated list of strings (event handler command line or
  command line templates).
- *default*: (none)
- *example*: ``handlers = my-handler.sh``


[cylc] ``->`` [[events]] ``->`` handler events
""""""""""""""""""""""""""""""""""""""""""""""

Specify the events for which the general event handlers should be invoked.

- *type*: Comma-separated list of events
- *default*: (none)
- *example*: ``handler events = timeout, shutdown``


[cylc] ``->`` [[events]] ``->`` mail events
"""""""""""""""""""""""""""""""""""""""""""

Specify the suite events for which notification emails should be sent.

- *type*: Comma-separated list of events
- *default*: (none)
- *example*: ``mail events = startup, shutdown, timeout``


[cylc] ``->`` [[events]] ``->`` mail footer
"""""""""""""""""""""""""""""""""""""""""""

Specify a string or string template to insert to footers of notification emails
for both suite events and task events.

A template string may have any or all of these patterns which will be
substituted with actual values:

- \%(host)s: suite host name
- \%(port)s: suite port number
- \%(owner)s: suite owner name
- \%(suite)s: suite name

- *type*: 
- *default*: (none)
- *example*:
  ``mail footer = see: http://localhost/%(owner)s/notes-on/%(suite)s/``


[cylc] ``->`` [[events]] ``->`` mail from
"""""""""""""""""""""""""""""""""""""""""

Specify an alternate ``from:`` email address for suite event notifications.

- *type*: string
- *default*: None, (notifications@HOSTNAME)
- *example*: ``mail from = no-reply@your-org``


[cylc] ``->`` [[events]] ``->`` mail smtp
"""""""""""""""""""""""""""""""""""""""""

Specify the SMTP server for sending suite event email notifications.

- *type*: string
- *default*: None, (localhost:25)
- *example*: ``mail smtp = smtp.yourorg``


[cylc] ``->`` [[events]] ``->`` mail to
"""""""""""""""""""""""""""""""""""""""

A list of email addresses to send suite event notifications. The list can be
anything accepted by the ``mail`` command.

- *type*: string
- *default*: None, (USER@HOSTNAME)
- *example*: ``mail to = your.colleague``


[cylc] ``->`` [[events]] ``->`` timeout
"""""""""""""""""""""""""""""""""""""""

If a timeout is set and the timeout event is handled, the timeout event
handler(s) will be called if the suite stays in a stalled state for some period
of time. The timer is set initially at suite start up. It is possible to set a
default for this at the site level (see :ref:`SiteCylcHooks`).

- *type*: ISO 8601 duration/interval representation (e.g. 
  ``PT5S``, 5 seconds, ``PT1S``, 1 second) - minimum 0 seconds.
- *default*: (none), unless set at the site level.


[cylc] ``->`` [[events]] ``->`` inactivity
""""""""""""""""""""""""""""""""""""""""""

If inactivity is set and the inactivity event is handled, the inactivity event
handler(s) will be called if there is no activity in the suite for some period
of time. The timer is set initially at suite start up. It is possible to set a
default for this at the site level (see :ref:`SiteCylcHooks`).

- *type*: ISO 8601 duration/interval representation (e.g.  
  ``PT5S``, 5 seconds, ``PT1S``, 1 second) - minimum 0 seconds.
- *default*: (none), unless set at the site level.


[cylc] ``->`` [[events]] ``->`` abort on stalled
""""""""""""""""""""""""""""""""""""""""""""""""

If this is set to True it will cause the suite to abort with error status
if it stalls. A suite is considered "stalled" if there are no active,
queued or submitting tasks or tasks waiting for clock triggers to be met. It is
possible to set a default for this at the site level
(see :ref:`SiteCylcHooks`).

- *type*: boolean
- *default*: False, unless set at the site level.


[cylc] ``->`` [[events]] ``->`` abort on timeout
""""""""""""""""""""""""""""""""""""""""""""""""

If a suite timer is set (above) this will cause the suite to abort with
error status if the suite times out while still running. It is possible to set
a default for this at the site level (see :ref:`SiteCylcHooks`).

- *type*: boolean
- *default*: False, unless set at the site level.


[cylc] ``->`` [[events]] ``->`` abort on inactivity
"""""""""""""""""""""""""""""""""""""""""""""""""""

If a suite inactivity timer is set (above) this will cause the suite to abort
with error status if the suite is inactive for some period while still running.
It is possible to set a default for this at the site level
(see :ref:`SiteCylcHooks`).

- *type*: boolean
- *default*: False, unless set at the site level.


[cylc] ``->`` [[events]] ``->`` abort if EVENT handler fails
""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

Cylc does not normally care whether an event handler succeeds or fails,
but if this is turned on the EVENT handler will be executed in the
foreground (which will block the suite while it is running) and the
suite will abort if the handler fails.

- *type*: boolean
- *default*: False


[cylc] ``->`` [[environment]]
"""""""""""""""""""""""""""""

Environment variables defined in this section are passed to suite and
task event handlers.

- These variables are not passed to tasks - use task runtime
  variables for that. Similarly, task runtime variables are not
  available to event handlers - which are executed by the suite server
  program, (not by running tasks) in response to task events.
- Cylc-defined environment variables such as
  ``$CYLC_SUITE_RUN_DIR`` are not passed to task event
  handlers by default, but you can make them available by
  extracting them to the cylc environment like this:

  .. code-block:: cylc

     [cylc]
         [[environment]]
             CYLC_SUITE_RUN_DIR = $CYLC_SUITE_RUN_DIR

- These variables - unlike task execution environment variables
  which are written to job scripts and interpreted by the shell at
  task run time - are not interpreted by the shell prior to use
  so shell variable expansion expressions cannot be used here.


[cylc] ``->`` [[environment]] ``->`` \_\_VARIABLE\_\_
"""""""""""""""""""""""""""""""""""""""""""""""""""""

Replace ``__VARIABLE__`` with any number of environment variable
assignment expressions.
Values may refer to other local environment variables (order of
definition is preserved) and are not evaluated or manipulated by
cylc, so any variable assignment expression that is legal in the
shell in which cylc is running can be used (but see the warning
above on variable expansions, which will not be evaluated).
White space around the ``=`` is allowed (as far as cylc's file
parser is concerned these are just suite configuration items).

- *type*: string
- *default*: (none)
- *examples*: ``FOO = $HOME/foo``


.. _ReferenceTestConfig:

[cylc] ``->`` [[reference test]]
""""""""""""""""""""""""""""""""

Reference tests are finite-duration suite runs that abort with non-zero
exit status if cylc fails, if any task fails, if the suite times
out, or if a shutdown event handler that (by default) compares the test
run with a reference run reports failure. See :ref:`AutoRefTests`.


[cylc] ``->`` [[reference test]] ``->`` suite shutdown event handler
""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

A shutdown event handler that should compare the test run with the
reference run, exiting with zero exit status only if the test run
verifies.

- *type*: string (event handler command name or path)
- *default*: ``cylc hook check-triggering``

As for any event handler, the full path can be omitted if the script is
located somewhere in ``$PATH`` or in the suite bin directory.


[cylc] ``->`` [[reference test]] ``->`` required run mode
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""

If your reference test is only valid for a particular run mode, this
setting will cause cylc to abort if a reference test is attempted
in another run mode.

- *type*: string
- *legal values*: live, dummy, dummy-local, simulation
- *default*: None


[cylc] ``->`` [[reference test]] ``->`` allow task failures
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

A reference test run will abort immediately if any task fails, unless
this item is set, or a list of *expected task failures* is provided
(below).

- *type*: boolean
- *default*: False


[cylc] ``->`` [[reference test]] ``->`` expected task failures
""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

A reference test run will abort immediately if any task fails, unless
*allow task failures* is set (above) or the failed task is found
in a list IDs of tasks that are expected to fail.

- *type*: Comma-separated list of strings (task IDs: ``name.cycle_point``).
- *default*: (none)
- *example*: ``foo.20120808, bar.20120908``


[cylc] ``->`` [[reference test]] ``->`` live mode suite timeout
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

The timeout value, expressed as an ISO 8601 duration/interval, after which the
test run should be aborted if it has not finished, in live mode. Test runs
cannot be done in live mode unless you define a value for this item, because
it is not possible to arrive at a sensible default for all suites.

- *type*: ISO 8601 duration/interval representation, e.g. 
  ``PT5M`` is 5 minutes (note: by contrast ``P5M`` means 5
  months, so remember the ``T``!).
- *default*: PT1M (1 minute)


[cylc] ``->`` [[reference test]] ``->`` simulation mode suite timeout
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

The timeout value in minutes after which the test run should be aborted
if it has not finished, in simulation mode. Test runs cannot be done in
simulation mode unless you define a value for this item, because it is
not possible to arrive at a sensible default for all suites.

- *type*: ISO 8601 duration/interval representation (e.g. 
  ``PT5M``, 5 minutes (note: by contrast, ``P5M`` means 5
  months, so remember the ``T``!)).
- *default*: PT1M (1 minute)


[cylc] ``->`` [[reference test]] ``->`` dummy mode suite timeout
""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

The timeout value, expressed as an ISO 8601 duration/interval, after which the
test run should be aborted if it has not finished, in dummy mode.  Test runs
cannot be done in dummy mode unless you define a value for this item, because
it is not possible to arrive at a sensible default for all suites.

- *type*: ISO 8601 duration/interval representation (e.g. 
  ``PT5M``, 5 minutes (note: by contrast, ``P5M`` means 5
  months, so remember the ``T``!)).
- *default*: PT1M (1 minute)


.. _SuiteAuth:

[cylc] ``->`` [[authentication]]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Authentication of client programs with suite server programs can be set in the
global site/user config files and overridden here if necessary.
See :ref:`GlobalAuth` for more information.


[cylc] ``->`` [[authentication]] ``->`` public
""""""""""""""""""""""""""""""""""""""""""""""

The client privilege level granted for public access - i.e. no suite passphrase
required.  See :ref:`GlobalAuth` for legal values.


[cylc] ``->`` [[simulation]]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Suite-level configuration for the *simulation* and *dummy* run modes
described in :ref:`SimulationMode`.


[cylc] ``->`` [[simulation]] ``->`` disable suite event handlers
""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

If this is set to ``True`` configured suite event handlers will not be
called in simulation or dummy modes.

- *type*: boolean
- *default*: ``True``


[scheduling]
------------

This section allows cylc to determine when tasks are ready to run.


.. _cycling-mode:

[scheduling] ``->`` cycling mode
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Cylc runs using the proleptic Gregorian calendar by default. This item allows
you to either run the suite using the 360 day calendar (12 months of 30 days
in a year) or using integer cycling. It also supports use of the 365 (never a
leap year) and 366 (always a leap year) calendars.

- *type*: string
- *legal values*: gregorian, 360day, 365day, 366day, integer
- *default*: gregorian


.. _initial cycle point:

[scheduling] ``->`` initial cycle point
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In a cold start each cycling task (unless specifically excluded under
``[special tasks]``) will be loaded into the suite with this cycle point,
or with the closest subsequent valid cycle point for the task.  This item can
be overridden on the command line.

In date-time cycling, if you do not provide time zone information for this,
it will be assumed to be local time, or in UTC if :ref:`UTC-mode` is set, or in
the time zone determined by :ref:`cycle-point-time-zone` if that is set.

- *type*: ISO 8601 date-time point representation (e.g. 
  ``CCYYMMDDThhmm``, 19951231T0630) or "now".
- *default*: (none)

The string "now" converts to the current date-time on the suite host (adjusted
to UTC if the suite is in UTC mode but the host is not) to minute resolution.
Minutes (or hours, etc.) may be ignored depending on your cycle point format
(:ref:`cycle-point-format`).


[scheduling] ``->`` [[initial cycle point]] ``->`` initial cycle point relative to current time
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This can be used to set the initial cycle point time relative to the
current time.

Two additional commands, ``next`` and ``previous``, can be used when setting
the initial cycle point.

The syntax uses truncated ISO8601 time representations, and is of the style:
``next(Thh:mmZ)``, ``previous(T-mm)``; e.g.

* ``initial cycle point = next(T15:00Z)``
* ``initial cycle point = previous(T09:00)``
* ``initial cycle point = next(T12)``
* ``initial cycle point = previous(T-20)``

Examples of interpretation are given in
:numref:`fig-relative-initial-cycle-point-time-syntax-interpretation`.

A list of times, separated by semicolons, can be provided, e.g.
``next(T-00;T-15;T-30;T-45)``. At least one time is required within the
brackets, and if more than one is given, the major time unit in each (hours
or minutes) should all be of the same type.

If an offset from the specified date or time is required, this should be
used in the form: ``previous(Thh:mm) +/- PxTy`` in the same way as is used
for determining cycle periods, e.g.

* ``initial cycle point = previous(T06) +P1D``
* ``initial cycle point = next(T-30) -PT1H``

The section in the bracket attached to the next/previous command is
interpreted first, and then the offset is applied.

The offset can also be used independently without a ``next`` or ``previous``
command, and will be interpreted as an offset from "now".

.. _fig-relative-initial-cycle-point-time-syntax-interpretation:

.. table:: Examples of setting relative initial cycle point for times and offsets using ``now = 2018-03-14T15:12Z`` (and UTC mode)

   ====================================  ==================
   Syntax                                Interpretation
   ====================================  ==================
   ``next(T-00)``                        2018-03-14T16:00Z
   ``previous(T-00)``                    2018-03-14T15:00Z
   ``next(T-00; T-15; T-30; T-45)``      2018-03-14T15:15Z
   ``previous(T-00; T-15; T-30; T-45)``  2018-03-14T15:00Z
   ``next(T00)``                         2018-03-15T00:00Z
   ``previous(T00)``                     2018-03-14T00:00Z
   ``next(T06:30Z)``                     2018-03-15T06:30Z
   ``previous(T06:30) -P1D``             2018-03-13T06:30Z
   ``next(T00; T06; T12; T18)``          2018-03-14T18:00Z
   ``previous(T00; T06; T12; T18)``      2018-03-14T12:00Z
   ``next(T00; T06; T12; T18) +P1W``     2018-03-21T18:00Z
   ``PT1H``                              2018-03-14T16:12Z
   ``-P1M``                              2018-02-14T15:12Z
   ====================================  ==================

The relative initial cycle point also works with truncated dates, including
weeks and ordinal date, using ISO8601 truncated date representations.
Note that day-of-week should always be specified when using weeks. If a time
is not included, the calculation of the next or previous corresponding
point will be done from midnight of the current day.
Examples of interpretation are given in
:numref:`fig-relative-initial-cycle-point-date-syntax-interpretation`.

.. _fig-relative-initial-cycle-point-date-syntax-interpretation:

.. table:: Examples of setting relative initial cycle point for dates using ``now = 2018-03-14T15:12Z`` (and UTC mode)

   ====================================  ==================
   Syntax                                Interpretation
   ====================================  ==================
   ``next(-00)``                         2100-01-01T00:00Z
   ``previous(--01)``                    2018-01-01T00:00Z
   ``next(---01)``                       2018-04-01T00:00Z
   ``previous(--1225)``                  2017-12-25T00:00Z
   ``next(-2006)``                       2020-06-01T00:00Z
   ``previous(-W101)``                   2018-03-05T00:00Z
   ``next(-W-1; -W-3; -W-5)``            2018-03-14T00:00Z
   ``next(-001; -091; -181; -271)``      2018-04-01T00:00Z
   ``previous(-365T12Z)``                2017-12-31T12:00Z
   ====================================  ==================


[scheduling] ``->`` final cycle point
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Cycling tasks are held once they pass the final cycle point, if one is
specified. Once all tasks have achieved this state the suite will shut
down. If this item is provided you can override it on the command line.

In date-time cycling, if you do not provide time zone information for this,
it will be assumed to be local time, or in UTC if :ref:`UTC-mode` is set, or in
the :ref:`cycle-point-time-zone` if that is set.

- *type*: ISO 8601 date-time point representation (e.g. 
  ``CCYYMMDDThhmm``, 19951231T1230) or ISO 8601 date-time offset
  (e.g.  +P1D+PT6H)
- *default*: (none)


.. _initial cycle point constraints:

[scheduling] ``->`` initial cycle point constraints
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In a cycling suite it is possible to restrict the initial cycle point by
defining a list of truncated time points under the initial cycle point
constraints.

- *type*: Comma-separated list of ISO 8601 truncated time point
  representations (e.g.  T00, T06, T-30).
- *default*: (none)


.. _final cycle point constraints:

[scheduling] ``->`` final cycle point constraints
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In a cycling suite it is possible to restrict the final cycle point by
defining a list of truncated time points under the final cycle point
constraints.

- *type*: Comma-separated list of ISO 8601 truncated time point
  representations (e.g. T00, T06, T-30).
- *default*: (none)


[scheduling] ``->`` hold after point
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Cycling tasks are held once they pass the hold after cycle point, if one is
specified. Unlike the final cycle point suite will not shut down once all tasks
have passed this point. If this item is provided you can override it on the
command line.


.. _runahead limit:

[scheduling] ``->`` runahead limit
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Runahead limiting prevents the fastest tasks in a suite from getting too far
ahead of the slowest ones, as documented in :ref:`RunaheadLimit`.

This config item specifies a hard limit as a cycle interval between the
slowest and fastest tasks. It is deprecated in favour of the newer default
limiting by ``max active cycle points`` (:ref:`max active cycle points`).

- *type*: Cycle interval string e.g. ``PT12H``
  for a 12 hour limit under ISO 8601 cycling.
- *default*: (none)


.. _max active cycle points:

[scheduling] ``->`` max active cycle points
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Runahead limiting prevents the fastest tasks in a suite from getting too far
ahead of the slowest ones, as documented in :ref:`RunaheadLimit`.

This config item supersedes the deprecated hard ``runahead limit``
(:ref:`runahead limit`). It allows up to ``N`` (default 3) consecutive
cycle points to be active at any time, adjusted up if necessary for
any future triggering.

- *type*: integer
- *default*: 3


.. _spawn to max active cycle points:

[scheduling] ``->`` spawn to max active cycle points
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Allows tasks to spawn out to ``max active cycle points``
(:ref:`max active cycle points`), removing restriction that a task has to have
submitted before its successor can be spawned.

*Important*: This should be used with care given the potential impact of
additional task proxies in terms of memory and cpu for the cylc server
program. Also, use
of the setting may highlight any issues with suite design relying on the
default behaviour where downstream tasks would otherwise be waiting on ones
upstream submitting and the suite would have stalled e.g. a housekeeping task
at a later cycle deleting an earlier cycle's data before that cycle has had
chance to run where previously the task would not have been spawned until its
predecessor had been submitted.

- *type*: boolean
- *default*: False


[scheduling] ``->`` [[queues]]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Configuration of internal queues, by which the number of simultaneously
active tasks (submitted or running) can be limited, per queue. By
default a single queue called *default* is defined, with all tasks
assigned to it and no limit. To use a single queue for the whole suite
just set the limit on the *default* queue as required.
See also :ref:`InternalQueues`.


[scheduling] ``->`` [[queues]] ``->`` [[[\_\_QUEUE\_\_]]]
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""

Section heading for configuration of a single queue. Replace
``__QUEUE__`` with a queue name, and repeat the section as required.

- *type*: string
- *default*: "default"


[scheduling] ``->`` [[queues]] ``->`` [[[\_\_QUEUE\_\_]]] ``->`` limit
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

The maximum number of active tasks allowed at any one time, for this queue.

- *type*: integer
- *default*: 0 (i.e. no limit)


[scheduling] ``->`` [[queues]] ``->`` [[[\_\_QUEUE\_\_]]] ``->`` members
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

A list of member tasks, or task family names, to assign to this queue
(assigned tasks will automatically be removed from the default queue).

- *type*: Comma-separated list of strings (task or family names).
- *default*: none for user-defined queues; all tasks for the "default" queue


[scheduling] ``->`` [[xtriggers]]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This section is for *External Trigger* function declarations -
see :ref:`External Triggers`.


[scheduling] ``->`` [[xtriggers]] ``->`` \_\_MANY\_\_
"""""""""""""""""""""""""""""""""""""""""""""""""""""

Replace ``__MANY__`` with any user-defined event trigger function
declarations and corresponding labels for use in the graph:

- *type*: string: function signature followed by optional call interval
- *example*: ``trig_1 = my_trigger(arg1, arg2, kwarg1, kwarg2):PT10S``

(See :ref:`External Triggers` for details).


[scheduling] ``->`` [[special tasks]]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This section is used to identify tasks with special behaviour. Family names can
be used in special task lists as shorthand for listing all member tasks.


[scheduling] ``->`` [[special tasks]] ``->`` clock-trigger
""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

.. note::

   Please read :ref:`External Triggers` before
   using the older clock triggers described in this section.

Clock-trigger tasks (see :ref:`ClockTriggerTasks`) wait on a wall clock time
specified as an offset from their own cycle point.

- *type*: Comma-separated list of task or family names with
  associated date-time offsets expressed as ISO8601 interval strings,
  positive or negative, e.g. ``PT1H`` for 1 hour.  The offset
  specification may be omitted to trigger right on the cycle point.
- *default*: (none)
- *example*:

  .. code-block:: cylc

     clock-trigger = foo(PT1H30M), bar(PT1.5H), baz


.. _ClockExpireRef:

[scheduling] ``->`` [[special tasks]] ``->`` clock-expire
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""

Clock-expire tasks enter the ``expired`` state and skip job submission if too
far behind the wall clock when they become ready to run.  The expiry time is
specified as an offset from wall-clock time; typically it should be negative -
see :ref:`ClockExpireTasks`.

- *type*: Comma-separated list of task or family names with
  associated date-time offsets expressed as ISO8601 interval strings,
  positive or negative, e.g. ``PT1H`` for 1 hour.  The offset
  may be omitted if it is zero.
- *default*: (none)
- *example*:

  .. code-block:: cylc

     clock-expire = foo(-P1D)


[scheduling] ``->`` [[special tasks]] ``->`` external-trigger
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

.. note::

   Please read :ref:`External Triggers` before
   using the older mechanism described in this section.

Externally triggered tasks (see :ref:`Old-Style External Triggers`) wait on
external events reported via the ``cylc ext-trigger`` command. To
constrain triggers to a specific cycle point, include
``$CYLC_TASK_CYCLE_POINT`` in the trigger message string and pass the
cycle point to the ``cylc ext-trigger`` command.

- *type*: Comma-separated list of task names with associated
  external trigger message strings.
- *default*: (none)
- *example*: (note the comma and line-continuation character)

  .. code-block:: none

     external-trigger = get-satx("new sat-X data ready"),
                        get-saty("new sat-Y data ready for $CYLC_TASK_CYCLE_POINT")


[scheduling] ``->`` [[special tasks]] ``->`` sequential
"""""""""""""""""""""""""""""""""""""""""""""""""""""""

Sequential tasks automatically depend on their own previous-cycle instance.
This declaration is deprecated in favour of explicit inter-cycle triggers -
see :ref:`SequentialTasks`.

- *type*: Comma-separated list of task or family names.
- *default*: (none)
- *example*: ``sequential = foo, bar``


.. _EASU:

[scheduling] ``->`` [[special tasks]] ``->`` exclude at start-up
""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

Any task listed here will be excluded from the initial task pool (this
goes for suite restarts too). If an *inclusion* list is also
specified, the initial pool will contain only included tasks that have
not been excluded. Excluded tasks can still be inserted at run time.
Other tasks may still depend on excluded tasks if they have not been
removed from the suite dependency graph, in which case some manual
triggering, or insertion of excluded tasks, may be required.

- *type*: Comma-separated list of task or family names.
- *default*: (none)


.. _IASU:

[scheduling] ``->`` [[special tasks]] ``->`` include at start-up
""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

If this list is not empty, any task *not* listed in it will be
excluded from the initial task pool (this goes for suite restarts too).
If an *exclusion* list is also specified, the initial pool will
contain only included tasks that have not been excluded. Excluded tasks
can still be inserted at run time. Other tasks may still depend on
excluded tasks if they have not been removed from the suite dependency
graph, in which case some manual triggering, or insertion of excluded
tasks, may be required.

- *type*: Comma-separated list of task or family names.
- *default*: (none)


[scheduling] ``->`` [[dependencies]]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The suite dependency graph is defined under this section.  You can plot
the dependency graph as you work on it, with ``cylc graph`` or
by right clicking on the suite in the db viewer.  See
also :ref:`ConfiguringScheduling`.


[scheduling] ``->`` [[dependencies]] ``->`` graph
"""""""""""""""""""""""""""""""""""""""""""""""""

The dependency graph for a completely non-cycling suites can go here.
See also :ref:`GraphDescrip` below and :ref:`ConfiguringScheduling`, for graph
string syntax.

- *type*: string
- *example*: (see :ref:`GraphDescrip` below)


[scheduling] ``->`` [[dependencies]] ``->`` [[[\_\_RECURRENCE\_\_]]]
""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

``__RECURRENCE__`` section headings define the sequence of cycle points for
which the subsequent graph section is valid. These should be specified in
our ISO 8601 derived sequence syntax, or similar for integer cycling:

- *examples*:
  - date-time cycling: ``[[[T00,T06,T12,T18]]]`` or ``[[[PT6H]]]``
  - integer cycling (stepped by 2): ``[[[P2]]]``
- *default*: (none)


See :ref:`GraphTypes` for more on recurrence expressions, and how multiple
graph sections combine.


.. _GraphDescrip:

[scheduling] ``->`` [[dependencies]] ``->`` [[[\_\_RECURRENCE\_\_]]] ``->`` graph
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

The dependency graph for a given recurrence section goes here. Syntax examples
follow; see also :ref:`ConfiguringScheduling` and :ref:`TriggerTypes`.

- *type*: string
- *examples*:

  .. code-block:: cylc

     graph = """
         foo => bar => baz & waz     # baz and waz both trigger off bar
         foo[-P1D-PT6H] => bar       # bar triggers off foo[-P1D-PT6H]
         baz:out1 => faz             # faz triggers off a message output of baz
         X:start => Y                # Y triggers if X starts executing
         X:fail => Y                 # Y triggers if X fails
         foo[-PT6H]:fail => bar      # bar triggers if foo[-PT6H] fails
         X => !Y                     # Y suicides if X succeeds
         X | X:fail => Z             # Z triggers if X succeeds or fails
         X:finish => Z               # Z triggers if X succeeds or fails
         (A | B & C ) | D => foo     # general conditional triggers
         foo:submit => bar           # bar triggers if foo is successfully submitted
         foo:submit-fail => bar      # bar triggers if submission of foo fails
         # comment
     """

- *default*: (none)


[runtime]
---------

This section is used to specify how, where, and what to execute when
tasks are ready to run. Common
configuration can be factored out in a multiple-inheritance hierarchy of
runtime namespaces that culminates in the tasks of the suite. Order of
precedence is determined by the C3 linearization algorithm as used to
find the *method resolution order* in Python language class
hierarchies. For details and examples see :ref:`NIORP`.


[runtime] ``->`` [[\_\_NAME\_\_]]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Replace ``__NAME__`` with a namespace name, or a comma-separated list of
names, and repeat as needed to define all tasks in the suite. Names may
contain letters, digits, underscores, and hyphens. A namespace
represents a group or family of tasks if other namespaces inherit from
it, or a task if no others inherit from it.

  Names may not contain colons (which would preclude use of directory paths
  involving the registration name in ``$PATH`` variables). They
  may not contain the "." character (it will be interpreted as the
  namespace hierarchy delimiter, separating groups and names -huh?).

- *legal values*:
  - ``[[foo]]``
  - ``[[foo, bar, baz]]``

If multiple names are listed the subsequent settings apply to each.

All namespaces inherit initially from *root*, which can be
explicitly configured to provide or override default settings
for all tasks in the suite.


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` extra log files
""""""""""""""""""""""""""""""""""""""""""""""""""""""""

A list of user-defined log files associated with a task. Log files
must reside in the job log directory ``$CYLC_TASK_LOG_DIR`` and ideally
should be named using the ``$CYLC_TASK_LOG_ROOT`` prefix
(see :ref:`Task Job Script Variables`).

- *type*: Comma-separated list of strings (log file names).
- *default*: (none)
- *example*: (job.custom-log-name)


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` inherit
""""""""""""""""""""""""""""""""""""""""""""""""

A list of the immediate parent(s) this namespace inherits from. If no
parents are listed ``root`` is assumed.

- *type*: Comma-separated list of strings (parent namespace names).
- *default*: ``root``


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` init-script
""""""""""""""""""""""""""""""""""""""""""""""""""""

Custom script invoked by the task job script before the task execution
environment is configured - so it does not have access to any suite or task
environment variables. It can be an external command or script, or inlined
scripting. The original intention for this item was to allow remote tasks to
source login scripts to configure their access to cylc, but this should no
longer be necessary (see :ref:`HowTasksGetAccessToCylc`). See also
``env-script``, ``pre-script``, ``script``,
``post-script``, ``err-script``, ``exit-script``.

- *type*: string
- *default*: (none)
- *example*: ``init-script = "echo Hello World"``


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` env-script
"""""""""""""""""""""""""""""""""""""""""""""""""""

Custom script invoked by the task job script between the cylc-defined environment
(suite and task identity, etc.) and the user-defined task runtime environment -
so it has access to the cylc environment (and the task environment has
access to variables defined by this scripting). It can be an external command
or script, or inlined scripting. See also ``init-script``,
``pre-script``, ``script``, ``post-script``,
``err-script``, and ``exit-script``.

- *type*: string
- *default*: (none)
- *example*: ``env-script = "echo Hello World"``


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` pre-script
"""""""""""""""""""""""""""""""""""""""""""""""""""

Custom script invoked by the task job script immediately before the ``script``
item (just below). It can be an external command or script, or inlined scripting.
See also ``init-script``, ``env-script``,
``script``, ``post-script``, ``err-script``, and
``exit-script``.

- *type*: string
- *default*: (none)
- *example*:

  .. code-block:: cylc

     pre-script = """
       . $HOME/.profile
       echo Hello from suite ${CYLC_SUITE_NAME}!"""


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` script
"""""""""""""""""""""""""""""""""""""""""""""""

The main custom script invoked from the task job script. It can be an
external command or script, or inlined scripting. See also
``init-script``, ``env-script``, ``pre-script``,
``post-script``, ``err-script``, and ``exit-script``.

- *type*: string
- *root default*: (none)


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` post-script
""""""""""""""""""""""""""""""""""""""""""""""""""""

Custom script invoked by the task job script immediately after the
``script`` item (just above). It can be an external command or script,
or inlined scripting.  See also
``init-script``, ``env-script``, ``pre-script``,
``script``, ``err-script``, and ``exit-script``.

- *type*: string
- *default*: (none)


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` err-script
"""""""""""""""""""""""""""""""""""""""""""""""""""

Custom script to be invoked at the end of the error trap, which is triggered
due to failure of a command in the task job script or trappable job kill. The
output of this will always be sent to STDERR and ``$1`` is set to the
name of the signal caught by the error trap. The script should be fast and use
very little system resource to ensure that the error trap can return quickly.
Companion of ``exit-script``, which is executed on job success.
It can be an external command or script, or inlined scripting. See also
``init-script``, ``env-script``, ``pre-script``,
``script``, ``post-script``, and ``exit-script``.

- *type*: string
- *default*: (none)
- *example*: ``err-script = "printenv FOO"``


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` exit-script
""""""""""""""""""""""""""""""""""""""""""""""""""""

Custom script invoked at the very end of *successful* job execution, just
before the job script exits. It should execute very quickly. Companion of
``err-script``, which is executed on job failure. It can be an external
command or script, or inlined scripting. See also ``init-script``,
``env-script``, ``pre-script``, ``script``,
``post-script``, and ``err-script``.

- *type*: string
- *default*: (none)
- *example*: ``exit-script = "rm -f $TMP_FILES"``


.. _worksubdirectory:

[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` work sub-directory
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

Task job scripts are executed from within *work directories* created
automatically under the suite run directory. A task can get its own work
directory from ``$CYLC_TASK_WORK_DIR`` (or simply ``$PWD`` if
it does not ``cd`` elsewhere at runtime). The default directory
path contains task name and cycle point, to provide a unique workspace for
every instance of every task. If several tasks need to exchange files and
simply read and write from their from current working directory, this item
can be used to override the default to make them all use the same workspace.

The top level share and work directory location can be changed (e.g. to a
large data area) by a global config setting (see :ref:`workdirectory`).

- *type*: string (directory path, can contain environment variables)
- *default*: ``$CYLC_TASK_CYCLE_POINT/$CYLC_TASK_NAME``
- *example*: ``$CYLC_TASK_CYCLE_POINT/shared/``

.. note::

   If you omit cycle point from the work sub-directory path successive
   instances of the task will share the same workspace. Consider the effect
   on cycle point offset housekeeping of work directories before doing this.


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[meta]]]
"""""""""""""""""""""""""""""""""""""""""""""""""""

Section containing metadata items for this task or family namespace.
Several items (title, description, URL) are pre-defined and are used by
Cylc. Others can be user-defined and passed to task event handlers to be
interpreted according to your needs. For example, the value of an
"importance" item could determine how an event handler responds to task
failure events.

Any suite meta item can now be passed to task event handlers by prefixing the
string template item name with "suite\_", for example:

.. code-block:: cylc

   [runtime]
       [[root]]
           [[[events]]]
               failed handler = send-help.sh %(suite_title)s %(suite_importance)s %(title)s


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[meta]]] ``->`` title
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

A single line description of this namespace. It is displayed by the
``cylc list`` command and can be retrieved from running tasks
with the ``cylc show`` command.

- *type*: single line string
- *root default*: (none)


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[meta]]] ``->`` description
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

A multi-line description of this namespace, retrievable from running tasks with the
``cylc show`` command.

- *type*: multi-line string
- *root default*: (none)


.. _TaskURL:

[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[meta]]] ``->`` URL
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

A web URL to task documentation for this suite.  If present it can be browsed
with the ``cylc doc`` command. The string templates ``%(suite_name)s`` and
``%(task_name)s`` will be replaced with the actual suite and task names.
See also :ref:`SuiteURL`.

- *type*: string (URL)
- *default*: (none)
- *example*: you can set URLs to all tasks in a suite by putting
  something like the following in the root namespace:

  .. code-block:: cylc

     [runtime]
         [[root]]
             [[[meta]]]
                 URL = http://my-site.com/suites/%(suite_name)s/%(task_name)s.html

.. note::

   URLs containing the comment delimiter ``#`` must be protected by quotes.


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[meta]]] ``->`` \_\_MANY\_\_
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

Replace ``__MANY__`` with any user-defined metadata item. These, like title,
URL, etc. can be passed to task event handlers to be interpreted according to your
needs. For example, the value of an "importance" item could determine how an event
handler responds to task failure events.

- *type*: String or integer
- *default*: (none)
- *example*:

  .. code-block:: cylc

     [runtime]
         [[root]]
             [[[meta]]]
                 importance = high
                 color = red


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[job]]]
""""""""""""""""""""""""""""""""""""""""""""""""""

This section configures the means by which cylc submits task job scripts
to run.


.. _RuntimeJobSubMethods:

[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[job]]] ``->`` batch system
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

See :ref:`TaskJobSubmission` for how job submission works, and how to define
new handlers for different batch systems. Cylc has a number of built in batch
system handlers:

- *type*: string
- *legal values*:

  - ``background`` - invoke a child process
  - ``at`` - the rudimentary Unix ``at`` scheduler
  - ``loadleveler`` - IBM LoadLeveler ``llsubmit``, with directives
    defined in the suite.rc file
  - ``lsf`` - IBM Platform LSF ``bsub``, with directives defined in the
    suite.rc file
  - ``pbs`` - PBS ``qsub``, with directives defined in the suite.rc file
  - ``sge`` - Sun Grid Engine ``qsub``, with directives defined in the
    suite.rc file
  - ``slurm`` - Simple Linux Utility for Resource Management ``sbatch``, with
    directives defined in the suite.rc file
  - ``moab`` - Moab workload manager ``msub``, with directives defined in the
    suite.rc file

- *default*: ``background``


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[job]]] ``->`` execution time limit
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

Specify the execution wall clock limit for a job of the task.
For ``background`` and ``at``, the job script will be invoked using the ``timeout``
command. For other batch systems, the specified time will be automatically
translated into the equivalent directive for wall clock limit.

Tasks are polled multiple times, where necessary, when they exceed their
execution time limits. (See :ref:`ExecutionTimeLimitPollingIntervals` for
how to configure the polling intervals).

    - *type*: ISO 8601 duration/interval representation
    - *example*: ``PT5M``, 5 minutes, ``PT1H``, 1 hour
    - *default*: (none)


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[job]]] ``->`` batch submit command template
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

This allows you to override the actual command used by the chosen batch
system. The template's ``\%(job)s`` will be substituted by the
job file path.

- *type*: string
- *legal values*: a string template
- *example*: ``llsubmit \%(job)s``


.. _JobSubRefRetries:

[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[job]]] ``->`` submission retry delays
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

A list of duration (in ISO 8601 syntax), after which to resubmit if job
submission fails.

- *type*: Comma-separated list of ISO 8601 duration/interval
  representations, optionally *preceded* by multipliers.
- *example*: ``PT1M,3*PT1H, P1D`` is equivalent to
  ``PT1M, PT1H, PT1H, PT1H, P1D`` - 1 minute, 1 hour, 1 hour, 1
  hour, 1 day.
- *default*: (none)


.. _RefRetries:

[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[job]]] ``->`` execution retry delays
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

See also :ref:`TaskRetries`.

A list of ISO 8601 time duration/intervals after which to resubmit the task
if it fails. The variable ``$CYLC_TASK_TRY_NUMBER`` in the task
execution environment is incremented each time, starting from 1 for the
first try - this can be used to vary task behaviour by try number.

- *type*: Comma-separated list of ISO 8601 duration/interval representations,
  optionally *preceded* by multipliers.
- *example*: ``PT1.5M,3*PT10M`` is equivalent to
  ``PT1.5M, PT10M, PT10M, PT10M`` - 1.5 minutes, 10 minutes, 10 minutes, 10 minutes.
- *default*: (none)


.. _SubmissionPollingIntervals:

[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[job]]] ``->`` submission polling intervals
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

A list of intervals, expressed as ISO 8601 duration/intervals, with optional
multipliers, after which cylc will poll for status while the task is in the
submitted state.

For the polling task communication method this overrides the default
submission polling interval in the site/user config files
(:ref:`SiteAndUserConfiguration`). For default and ssh task communications,
polling is not done by default but it can still be configured here as a
regular check on the health of submitted tasks.

Each list value is used in turn until the last, which is used repeatedly
until finished.

- *type*: Comma-separated list of ISO 8601 duration/interval
  representations, optionally *preceded* by multipliers.
- *example*: ``PT1M,3*PT1H, PT1M`` is equivalent to
  ``PT1M, PT1H, PT1H, PT1H, PT1M`` - 1 minute, 1 hour, 1 hour, 1
  hour, 1 minute.
- *default*: (none)

A single interval value is probably appropriate for submission polling.


.. _ExecutionPollingIntervals:

[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[job]]] ``->`` execution polling intervals
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

A list of intervals, expressed as ISO 8601 duration/intervals, with optional
multipliers, after which cylc will poll for status while the task is in the
running state.

For the polling task communication method this overrides the default
execution polling interval in the site/user config files
(:ref:`SiteAndUserConfiguration`). For default and ssh task communications,
polling is not done by default but it can still be configured here as a
regular check on the health of submitted tasks.

Each list value is used in turn until the last, which is used repeatedly
until finished.

- *type*: Comma-separated list of ISO 8601 duration/interval
  representations, optionally *preceded* by multipliers.
- *example*: ``PT1M,3*PT1H, PT1M`` is equivalent to
  ``PT1M, PT1H, PT1H, PT1H, PT1M`` - 1 minute, 1 hour, 1 hour, 1
  hour, 1 minute.
- *default*: (none)


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[remote]]]
"""""""""""""""""""""""""""""""""""""""""""""""""""""

Configure host and username, for tasks that do not run on the suite host
account. Non-interactive ssh is used to submit the task by the configured
batch system, so you must distribute your ssh key to allow
this. Cylc must be installed on task remote accounts, but no external
software dependencies are required there.


.. _DynamicHostSelection:

[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[remote]]] ``->`` host
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

The remote host for this namespace. This can be a static hostname, an
environment variable that holds a hostname, or a command that prints a
hostname to stdout. Host selection commands are executed just prior to
job submission. The host (static or dynamic) may have an entry in the
cylc site or user config file to specify parameters such as the location
of cylc on the remote machine; if not, the corresponding local settings
(on the suite host) will be assumed to apply on the remote host.

- *type*: string (a valid hostname on the network)
- *default*: (none)
- *examples*:

  - static host name: ``host = foo``
  - fully qualified: ``host = foo.bar.baz``
  - dynamic host selection:

    - shell command (1): ``host = $(host-selector.sh)``
    - shell command (2): ``host = \`host-selector.sh\```
    - environment variable: ``host = $MY_HOST``


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[remote]]] ``->`` owner
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

The username of the task host account. This is (only) used in the
non-interactive ssh command invoked by the suite server program to submit the
remote task (consequently it may be defined using local environment variables
(i.e. the shell in which cylc runs, and ``[cylc] -> [[environment]]``).

If you use dynamic host selection and have different usernames on
the different selectable hosts, you can configure your
``$HOME/.ssh/config`` to handle username translation.

- *type*: string (a valid username on the remote host)
- *default*: (none)


.. _runtime-remote-retrieve-job-logs:

[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[remote]]] ``->`` retrieve job logs
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

Remote task job logs are saved to the suite run directory on the task host, not
on the suite host. If you want the job logs pulled back to the suite host
automatically, you can set this item to ``True``. The suite will
then attempt to ``rsync`` the job logs once from the remote host each
time a task job completes. E.g. if the job file is
``~/cylc-run/my-suite/log/job/1/hello/01/job``, anything under
``~/cylc-run/my-suite/log/job/1/hello/01/`` will be retrieved.

- *type*: boolean
- *default*: False


.. _runtime-remote-retrieve-job-logs-max-size:

[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[remote]]] ``->`` retrieve job logs max size
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

If the disk space of the suite host is limited, you may want to set the maximum
sizes of the job log files to retrieve. The value can be anything that is
accepted by the ``--max-size=SIZE`` option of the ``rsync`` command.

- *type*: string
- *default*: None


.. _runtime-remote-retrieve-job-logs-retry-delays:

[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[remote]]] ``->`` retrieve job logs retry delays
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

Some batch systems have considerable delays between the time when the job
completes and when it writes the job logs in its normal location. If this is
the case, you can configure an initial delay and some retry delays between
subsequent attempts. The default behaviour is to attempt once without any delay.

- *type*: Comma-separated list of ISO 8601 duration/interval representations, optionally
  *preceded* by multipliers.
- *default*: (none)
- *example*: ``retrieve job logs retry delays = PT10S, PT1M, PT5M``


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[remote]]] ``->``  suite definition directory
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

The path to the suite configuration directory on the remote account, needed if
remote tasks require access to files stored there (via
``$CYLC_SUITE_DEF_PATH``) or in the suite bin directory (via
``$PATH``).  If this item is not defined, the local suite
configuration directory path will be assumed, with the suite owner's home
directory, if present, replaced by ``'$HOME'`` for
interpretation on the remote account.

- *type*: string (a valid directory path on the remote account)
- *default*: (local suite configuration path with ``$HOME`` replaced)


.. _TaskEventHandling:

[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[events]]]
"""""""""""""""""""""""""""""""""""""""""""""""""""""

Cylc can call nominated event handlers when certain task events occur. This
section configures specific task event handlers; see :ref:`SuiteEventHandling`
for suite events.

Event handlers can be located in the suite ``bin/`` directory,
otherwise it is up to you to ensure their location is in ``$PATH`` (in
the shell in which the suite server program runs). They should require little
resource to run and return quickly.

Each task event handler can be specified as a list of command lines or command
line templates. They can contain any or all of the following patterns, which
will be substituted with actual values:

- \%(event)s: event name
- \%(suite)s: suite name
- \%(suite\_uuid)s: suite UUID string
- \%(point)s: cycle point
- \%(name)s: task name
- \%(submit\_num)s: submit number
- \%(try\_num)s: try number
- \%(id)s: task ID (i.e. \%(name)s.\%(point)s)
- \%(batch\_sys\_name)s: batch system name
- \%(batch\_sys\_job\_id)s: batch system job ID
- \%(message)s: event message, if any
- any task [meta] item, e.g.:
  - \%(title)s: task title
  - \%(URL)s: task URL
  - \%(importance)s - example custom task metadata
- any suite [meta] item, prefixed with "suite\_", e.g.:
  - \%(suite\_title)s: suite title
  - \%(suite\_URL)s: suite URL
  - \%(suite\_rating)s - example custom suite metadata

Otherwise, the command line will be called with the following default
arguments:

.. code-block:: none

   <task-event-handler> %(event)s %(suite)s %(id)s %(message)s

.. note::

   Substitution patterns should not be quoted in the template strings.
   This is done automatically where required.

For an explanation of the substitution syntax, see
`String Formatting Operations in the Python
documentation <https://docs.python.org/2/library/stdtypes.html#string-formatting>`_.

Additional information can be passed to event handlers via the
``[cylc] -> [[environment]]`` (but not via task
runtime environments - event handlers are not called by tasks).


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[events]]] ``->`` EVENT handler
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

A list of one or more event handlers to call when one of the following EVENTs occurs:

- **submitted** - the job submit command was successful
- **submission failed** - the job submit command failed, or the
  submitted job was killed before it started executing
- **submission retry** - job submit failed, but cylc will resubmit it
  after a configured delay
- **submission timeout** - the submitted job timed out without commencing execution
- **started** - the task reported commencement of execution
- **succeeded** - the task reported that it completed successfully
- **failed** - the task reported that if tailed to complete successfully
- **retry** - the task failed, but cylc will resubmit it
  after a configured delay
- **execution timeout** - the task timed out after execution commenced
- **warning** - the task reported a WARNING severity message
- **critical** - the task reported a CRITICAL severity message
- **custom** - the task reported a CUSTOM severity message
- **late** - the task is never active and is late

Item details:
- *type*: Comma-separated list of strings (event handler scripts).
- *default*: None
- *example*: ``failed handler = my-failed-handler.sh``


.. _runtime-event-hooks-submission-timeout:

[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[events]]] ``->`` submission timeout
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

If a task has not started after the specified ISO 8601 duration/interval, the
*submission timeout* event handler(s) will be called.

- *type*: ISO 8601 duration/interval representation (e.g.
  ``PT30M``, 30 minutes or ``P1D``, 1 day).
- *default*: (none)


.. _runtime-event-hooks-execution-timeout:

[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[events]]] ``->`` execution timeout
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

If a task has not finished after the specified ISO 8601 duration/interval, the
*execution timeout* event handler(s) will be called.

- *type*: ISO 8601 duration/interval representation (e.g.
  ``PT4H``, 4 hours or ``P1D``, 1 day).
- *default*: (none)


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[events]]] ``->`` handlers
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

Specify a list of command lines or command line templates as task event handlers.

- *type*: Comma-separated list of strings (event handler command line or command
  line templates).
- *default*: (none)
- *example*: ``handlers = my-handler.sh``


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[events]]] ``->`` handler events
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

Specify the events for which the general task event handlers should be invoked.

- *type*: Comma-separated list of events
- *default*: (none)
- *example*: ``handler events = submission failed, failed``


.. _runtime-events-handler-retry-delays:

[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[events]]] ``->`` handler retry delays
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

Specify an initial delay before running an event handler command and any retry
delays in case the command returns a non-zero code. The default behaviour is to
run an event handler command once without any delay.

- *type*: Comma-separated list of ISO 8601 duration/interval representations,
  optionally *preceded* by multipliers.
- *default*: (none)
- *example*: ``handler retry delays = PT10S, PT1M, PT5M``


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[events]]] ``->`` mail events
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

Specify the events for which notification emails should be sent.

- *type*: Comma-separated list of events
- *default*: (none)
- *example*: ``mail events = submission failed, failed``


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[events]]] ``->`` mail from
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

Specify an alternate ``from:`` email address for event notifications.

- *type*: string
- *default*: None, (notifications@HOSTNAME)
- *example*: ``mail from = no-reply@your-org``


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[events]]] ``->`` mail retry delays
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

Specify an initial delay before running the mail notification command and any
retry delays in case the command returns a non-zero code. The default behaviour
is to run the mail notification command once without any delay.

- *type*: Comma-separated list of ISO 8601 duration/interval representations,
  optionally *preceded* by multipliers.
- *default*: (none)
- *example*: ``mail retry delays = PT10S, PT1M, PT5M``


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[events]]] ``->`` mail smtp
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

Specify the SMTP server for sending email notifications.

- *type*: string
- *default*: None, (localhost:25)
- *example*: ``mail smtp = smtp.yourorg``


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[events]]] ``->`` mail to
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

A list of email addresses to send task event notifications. The list can be
anything accepted by the ``mail`` command.

- *type*: string
- *default*: None, (USER@HOSTNAME)
- *example*: ``mail to = your.colleague``


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[environment]]]
""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

The user defined task execution environment. Variables defined here can
refer to cylc suite and task identity variables, which are exported
earlier in the task job script, and variable assignment expressions can
use cylc utility commands because access to cylc is also configured
earlier in the script.  See also :ref:`TaskExecutionEnvironment`.


.. _AppendixTaskExecutionEnvironment:

[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[environment]]] ``->`` \_\_VARIABLE\_\_
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

Replace ``__VARIABLE__`` with any number of environment variable
assignment expressions. Order of definition is preserved so values can
refer to previously defined variables. Values are passed through to the task
job script without evaluation or manipulation by cylc, so any variable assignment
expression that is legal in the job submission shell can be used.
White space around the ``=`` is allowed (as far as cylc's suite.rc
parser is concerned these are just normal configuration items).

- *type*: string
- *default*: (none)
- *examples*, for the bash shell:

  - ``FOO = $HOME/bar/baz``
  - ``BAR = ${FOO}$GLOBALVAR``
  - ``BAZ = $( echo "hello world" )``
  - ``WAZ = ${FOO%.jpg}.png``
  - ``NEXT_CYCLE = $( cylc cycle-point --offset=PT6H )``
  - ``PREV_CYCLE = \`cylc cycle-point --offset=-PT6H```
  - ``ZAZ = "${FOO#bar}" # <-- QUOTED to escape the suite.rc comment character``


.. _EnvironmentFilter:

[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[environment filter]]]
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

This section contains environment variable inclusion and exclusion
lists that can be used to filter the inherited environment. *This is
not intended as an alternative to a well-designed inheritance hierarchy
that provides each task with just the variables it needs.* Filters can,
however, improve suites with tasks that inherit a lot of environment
they don't need, by making it clear which tasks use which variables.
They can optionally be used routinely as explicit "task environment
interfaces" too, at some cost to brevity, because they guarantee that
variables filtered out of the inherited task environment are not used.

.. note::

   Environment filtering is done after inheritance is completely
   worked out, not at each level on the way, so filter lists in higher-level
   namespaces only have an effect if they are not overridden by descendants.


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[environment filter]]] ``->`` include
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

If given, only variables named in this list will be included from the
inherited environment, others will be filtered out. Variables may also
be explicitly excluded by an ``exclude`` list.

- *type*: Comma-separated list of strings (variable names).
- *default*: (none)


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[environment filter]]] ``->`` exclude
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

Variables named in this list will be filtered out of the inherited
environment.  Variables may also be implicitly excluded by
omission from an ``include`` list.

- *type*: Comma-separated list of strings (variable names).
- *default*: (none)


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[parameter environment templates]]]
""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

The user defined task execution parameter environment templates. This is only
relevant for *parameterized tasks* - see :ref:`Parameterized Tasks Label`.


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[parameter environment templates]]] ``->`` \_\_VARIABLE\_\_
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

Replace ``__VARIABLE__`` with pairs of environment variable
name and Python string template for parameter substitution. This is only
relevant for *parameterized tasks* - see :ref:`Parameterized Tasks Label`.

If specified, in addition to the standard ``CYLC_TASK_PARAM_<key>``
variables, the job script will also export the named variables specified
here, with the template strings substituted with the parameter values.

- *type*: string
- *default*: (none)
- *legal values*: name=string template pairs
- *examples*, for the bash shell:

  - ``MYNUM=%(i)d``
  - ``MYITEM=%(item)s``
  - ``MYFILE=/path/to/%(i)03d/%(item)s``


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[directives]]]
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""

Batch queue scheduler directives.  Whether or not these are used depends
on the batch system. For the built-in methods that support directives
(``loadleveler``, ``lsf``, ``pbs``, ``sge``,
``slurm``, ``moab``), directives are written to the top of the
task job script in the correct format for the method. Specifying directives
individually like this allows use of default directives that can be
individually overridden at lower levels of the runtime namespace hierarchy.


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[directives]]] ``->`` \_\_DIRECTIVE\_\_
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

Replace ``__DIRECTIVE__`` with each directive assignment, e.g.
``class = parallel``.

- *type*: string
- *default*: (none)

Example directives for the built-in batch system handlers are shown
in :ref:`AvailableMethods`.


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[outputs]]]
""""""""""""""""""""""""""""""""""""""""""""""""""""""

Register custom task outputs for use in message triggering in this section
(:ref:`MessageTriggers`)


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[outputs]]] ``->`` \_\_OUTPUT\_\_
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

Replace ``__OUTPUT__`` with one or more custom task output messages
(:ref:`MessageTriggers`).  The item name is used to select the custom output
message in graph trigger notation.

- *type*: string
- *default*: (none)
- *examples*:

  .. code-block:: cylc

     out1 = "sea state products ready"
     out2 = "NWP restart files completed"



[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[suite state polling]]]
""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

Configure automatic suite polling tasks as described
in :ref:`SuiteStatePolling`. The
items in this section reflect the options and defaults of the
``cylc suite-state`` command, except that the target suite name and the
``--task``, ``--cycle``, and ``--status`` options are
taken from the graph notation.


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[suite state polling]]] ``->`` run-dir
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

For your own suites the run database location is determined by your
site/user config. For other suites, e.g. those owned by others, or
mirrored suite databases, use this item to specify the location
of the top level cylc run directory (the database should be a
suite-name sub-directory of this location).

- *type*: string (a directory path on the target suite host)
- *default*: as configured by site/user config (for your own suites)


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[suite state polling]]] ``->`` interval
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

Polling interval expressed as an ISO 8601 duration/interval.

- *type*: ISO 8601 duration/interval representation (e.g.
  ``PT10S``, 10 seconds, or ``PT1M``, 1 minute).
- *default*: PT1M


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[suite state polling]]] ``->`` max-polls
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

The maximum number of polls before timing out and entering the "failed" state.

- *type*: integer
- *default*: 10


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[suite state polling]]] ``->`` user
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

Username of an account on the suite host to which you have access. The
polling ``cylc suite-state`` command will be invoked
on the remote account.

- *type*: string (username)
- *default*: (none)


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[suite state polling]]] ``->`` host
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

The hostname of the target suite. The polling ``cylc suite-state`` command
will be invoked on the remote account.

- *type*: string (hostname)
- *default*: (none)


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[suite state polling]]] ``->`` message
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

Wait for the target task in the target suite to receive a specified message
rather than achieve a state.

- *type*: string (the message)
- *default*: (none)


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[suite state polling]]] ``->`` verbose
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

Run the polling ``cylc suite-state`` command in verbose output mode.

- *type*: boolean
- *default*: False


.. _suiterc-sim-config:

[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[simulation]]]
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""

Task configuration for the suite *simulation* and *dummy* run modes
described in :ref:`SimulationMode`.


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[simulation]]] ``->`` default run length
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

The default simulated job run length, if ``[job]execution time limit``
and ``[simulation]speedup factor`` are not set.

- *type*: ISO 8601 duration/interval representation (e.g.
  ``PT10S``, 10 seconds, or ``PT1M``, 1 minute).
- *default*: ``PT10S``


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[simulation]]] ``->`` speedup factor
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

If ``[job]execution time limit`` is set, the task simulated run length
is computed by dividing it by this factor.

- *type*: float
- *default*: (none) - i.e. do not use proportional run length
- *example*: ``10.0``


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[simulation]]] ``->`` time limit buffer
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

For dummy jobs, a new ``[job]execution time limit`` is set to the
simulated task run length plus this buffer interval, to avoid job kill due to
exceeding the time limit.

- *type*: ISO 8601 duration/interval representation (e.g.
  ``PT10S``, 10 seconds, or ``PT1M``, 1 minute).
- *default*: PT10S


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[simulation]]] ``->`` fail cycle points
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

Configure simulated or dummy jobs to fail at certain cycle points.

- *type*: list of strings (cycle points), or *all*
- *default*: (none) - no instances of the task will fail
- *examples*:
  - ``all`` - all instance of the task will fail
  - ``2017-08-12T06, 2017-08-12T18`` - these instances of the task will fail


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[simulation]]] ``->`` fail try 1 only
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

If this is set to ``True`` only the first run of the task instance will
fail, otherwise retries will fail too.

- *type*: boolean
- *default*: ``True``


[runtime] ``->`` [[\_\_NAME\_\_]] ``->`` [[[simulation]]] ``->`` disable task event handlers
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

If this is set to ``True`` configured task event handlers will not be called
in simulation or dummy modes.

- *type*: boolean
- *default*: ``True``


[visualization]
---------------

Configure the appearance of suites when displayed in Cylc visualisation tools.

[visualization] ``->`` initial cycle point
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The initial cycle point for graph plotting.

- *type*: ISO 8601 date-time representation (e.g. CCYYMMDDThhmm)
- *default*: the suite initial cycle point

The visualization initial cycle point gets adjusted up if necessary to the
suite initial cycling point.


[visualization] ``->`` final cycle point
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

An explicit final cycle point for graph plotting. If used, this overrides the
preferred *number of cycle points* (below).

- *type*: ISO 8601 date-time representation (e.g. CCYYMMDDThhmm)
- *default*: (none)

The visualization final cycle point gets adjusted down if necessary to the
suite final cycle point.


[visualization] ``->`` number of cycle points
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The number of cycle points to graph starting from the visualization initial
cycle point. This is the preferred way of defining the graph end point, but
it can be overridden by an explicit *final cycle point* (above).

- *type*: integer
- *default*: 3


[visualization] ``->`` collapsed families
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A list of family (namespace) names to be shown in the collapsed state
(i.e. the family members will be replaced by a single family node)
by default.
If this item is not set, the default is to collapse all families at first.

- *type*: Comma-separated list of family names.
- *default*: (none)


[visualization] ``->`` use node color for edges
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Plot graph edges (dependency arrows) with the same color as the upstream
node, otherwise default to black.

- *type*: boolean
- *default*: False


[visualization] ``->`` use node fillcolor for edges
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Plot graph edges (i.e. dependency arrows) with the same fillcolor as the
upstream node, if it is filled, otherwise default to black.

- *type*: boolean
- *default*: False


[visualization] ``->`` node penwidth
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Line width of node shape borders.

- *type*: integer
- *default*: 2


[visualization] ``->`` edge penwidth
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Line width of graph edges (dependency arrows).

- *type*: integer
- *default*: 2


[visualization] ``->`` use node color for labels
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Graph node labels can be printed in the same color as the node outline.

- *type*: boolean
- *default*: False


[visualization] ``->`` default node attributes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Set the default attributes (color and style etc.) of graph nodes (tasks and families).
Attribute pairs must be quoted to hide the internal ``=`` character.

- *type*: Comma-separated list of quoted ``'attribute=value'`` pairs.
- *legal values*: see graphviz or pygraphviz documentation
- *default*: ``'style=filled', 'fillcolor=yellow', 'shape=box'``


[visualization] ``->`` default edge attributes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Set the default attributes (color and style etc.) of graph edges
(dependency arrows).  Attribute pairs must be quoted to hide the
internal ``=`` character.

- *type*: Comma-separated list of quoted ``'attribute=value'`` pairs.
- *legal values*: see graphviz or pygraphviz documentation
- *default*: ``'color=black'``


[visualization] ``->`` [[node groups]]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Define named groups of graph nodes (tasks and families) which can styled
en masse, by name, in ``[visualization] -> [[node attributes]]``.
Node groups are automatically defined for all task families, including
root, so you can style family and member nodes at once by family name.


[visualization] ``->`` [[node groups]] ``->`` __GROUP__
"""""""""""""""""""""""""""""""""""""""""""""""""""""""

Replace ``__GROUP__`` with each named group of tasks or families.

- *type*: Comma-separated list of task or family names.
- *default*: (none)
- *example*:

  - PreProc = foo, bar
  - PostProc = baz, waz


[visualization] ``->`` [[node attributes]]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Here you can assign graph node attributes to specific nodes, or to all
members of named groups defined in ``[visualization] -> [[node groups]]``.
Task families are automatically node groups. Styling of a
family node applies to all member nodes (tasks and sub-families), but
precedence is determined by ordering in the suite configuration.  For
example, if you style a family red and then one of its members green,
cylc will plot a red family with one green member; but if you style one
member green and then the family red, the red family styling will
override the earlier green styling of the member.


[visualization] ``->`` [[node attributes]] ``->`` \_\_NAME\_\_
""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

Replace ``__NAME__`` with each node or node group for style attribute
assignment.

- *type*: Comma-separated list of quoted ``'attribute=value'`` pairs.
- *legal values*: see the Graphviz or PyGraphviz documentation
- *default*: (none)
- *example* (with reference to the node groups defined above):

  - PreProc = 'style=filled', 'fillcolor=orange'
  - PostProc = 'color=red'
  - foo = 'style=filled'
