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
"""Define all legal items and values for cylc suite definition files."""

import re

from metomi.isodatetime.data import Calendar

from cylc.flow import LOG
from cylc.flow.parsec.exceptions import UpgradeError
from cylc.flow.parsec.config import ParsecConfig, ConfigNode as Conf
from cylc.flow.parsec.OrderedDict import OrderedDictWithDefaults
from cylc.flow.parsec.upgrade import upgrader, converter
from cylc.flow.parsec.validate import (
    DurationFloat, CylcConfigValidator as VDR, cylc_config_validate)
from cylc.flow.platforms import get_platform
from cylc.flow.task_events_mgr import EventData

# Regex to check whether a string is a command
REC_COMMAND = re.compile(r'(`|\$\()\s*(.*)\s*([`)])$')

with Conf(
    'flow.cylc',
    desc='''
        Defines a cylc suite configuration.

        Embedded Jinja2 code (see :ref:`Jinja`) must process to a valid
        raw flow.cylc file. See also :ref:`FlowConfigFile` for a descriptive
        overview of flow.cylc files, including syntax (:ref:`Syntax`).

        .. note::

           Prior to Cylc 8, this was named ``suite.rc``, but that
           name is now deprecated. The ``cylc run`` command will automatically
           symlink an existing ``suite.rc`` file to ``flow.cylc``.
    '''
) as SPEC:

    with Conf('meta', desc='''
        Section containing metadata items for this suite. Several items (title,
        description, URL) are pre-defined and are used by Cylc. Others can be
        user-defined and passed to suite event handlers to be interpreted
        according to your needs. For example, the value of a "suite-priority"
        item could determine how an event handler responds to failure events.
    '''):
        Conf('description', VDR.V_STRING, '', desc='''
            A multi-line description of the suite. It can be retrieved at run
            time with the ``cylc show`` command.
        ''')
        Conf('title', VDR.V_STRING, '', desc='''
            A single line description of the suite, can be retrieved at run
            time with the ``cylc show`` command.
        ''')
        Conf('URL', VDR.V_STRING, '', desc='''
            A web URL to suite documentation.  If present it can be browsed
            with the ``cylc doc`` command. The string template
            ``%(suite_name)s`` will be replaced with the actual suite name.
            See also :cylc:conf:`flow.cylc[runtime][<namespace>][meta]URL`.

            Example:

            ``http://my-site.com/suites/%(suite_name)s/index.html``
        ''')
        Conf('<custom metadata>', VDR.V_STRING, '', desc='''
            Any user-defined metadata item. These,
            like title, URL, etc. can be passed to suite event handlers to be
            interpreted according to your needs. For example,
            "suite-priority".
        ''')
    with Conf('scheduler'):
        Conf('UTC mode', VDR.V_BOOLEAN)

        Conf('install', VDR.V_STRING_LIST, desc='''
            Configure the directories and files to be included in the remote
            file installation.

             .. note::
                These, as standard, include the following directories:

                 * app
                 * bin
                 * etc
                 * lib

                 And include the server.key file (from the .service
                 directory), this is required for authentication.

            These should be located in the top level of your Cylc workflow,
            i.e. the directory that contains your flow.cylc file.

            Directories must have a trailing slash.
            For example, to add the following items to your file installation:

            .. code-block:: none

                ~/cylc-run/workflow_x
                |__dir1/
                |__dir2/
                |__file1
                |__file2

            .. code-block:: cylc

                [scheduler]
                    install = dir/, dir2/, file1, file2
                ''')

        Conf('cycle point format', VDR.V_CYCLE_POINT_FORMAT, desc='''
            Set the date-time format that Cylc uses for
            :term:`cycle points<cycle point>` in :term:`datetime cycling`
            workflows.

            To just alter the timezone used in the date-time cycle point
            format, see :cylc:conf:`flow.cylc[scheduler]cycle point time zone`.
            To just alter the number of expanded year digits (for years
            below 0 or above 9999), see
            :cylc:conf:
            `flow.cylc[scheduler]cycle point num expanded year digits`.

            Cylc usually uses a ``CCYYMMDDThhmmZ`` (``Z`` in the special
            case of UTC) or ``CCYYMMDDThhmm±hhmm`` format for writing
            date-time cycle points, following the :term:`ISO8601` standard.

            You may use the `isodatetime library's syntax
            <https://github.com/metomi/isodatetime#dates-and-times>`_ to set
            the cycle point format, as demonstrated in the previous paragraph.

            You can also use a subset of the strptime/strftime POSIX
            standard - supported tokens are ``%F``, ``%H``, ``%M``, ``%S``,
            ``%Y``, ``%d``, ``%j``, ``%m``, ``%s``, ``%z``.

            The time zone you specify here will be used only for
            writing/dumping cycle points. Cycle points that are input without
            time zones will still default to the local time zone unless
            :cylc:conf:`flow.cylc[scheduler]cycle point time zone` or
            :cylc:conf:`flow.cylc[scheduler]UTC mode` are set. Not specifying a
            time zone here is inadvisable as it leads to ambiguity.

            .. note::

               The ISO8601 extended date-time format can be used
               (``CCYY-MM-DDThh:mm``) but note that the "-" and ":" characters
               end up in job log directory paths.
        ''')
        Conf('cycle point num expanded year digits', VDR.V_INTEGER, 0, desc='''
            For years below 0 or above 9999, the ISO 8601 standard specifies
            that an extra number of year digits and a sign should be used.
            This extra number needs to be written down somewhere (here).

            For example, if this extra number is set to 2, 00Z on the 1st of
            January in the year 10040 will be represented as
            ``+0100400101T0000Z`` (2 extra year digits used). With this number
            set to 3, 06Z on the 4th of May 1985 would be written as
            ``+00019850504T0600Z``.

            This number defaults to 0 (no sign or extra digits used).
        ''')
        Conf('cycle point time zone', VDR.V_CYCLE_POINT_TIME_ZONE, desc='''
            You may set your own time zone choice here, which will be used for
            date-time cycle point dumping and inferring the time zone of cycle
            points that are input without time zones.

            Time zones should be expressed as :term:`ISO8601` time zone offsets
            from UTC, such as ``+13``, ``+1300``, ``-0500`` or ``+0645``,
            with ``Z`` representing the special ``+0000`` case. Cycle points
            will be converted to the time zone you give and will be
            represented with this string at the end.

            If this isn't set (and :cylc:conf:`flow.cylc[scheduler]UTC mode`
            is also not set), then it will default to the local time zone at
            the time of running the suite. This will persist over local time
            zone changes (e.g. if the suite is run during winter time, then
            stopped, then restarted after summer time has begun, the cycle
            points will remain in winter time).

            If this isn't set, and UTC mode is set to True, then this will
            default to ``Z``. If you use a custom
            :cylc:conf:`flow.cylc[scheduler]cycle point format`, it is a good
            idea to set the same time zone here. If you specify a different
            one here, it will only be used for inferring timezone-less cycle
            points, while dumping will use the one from the cycle point format.

            .. note::

               It is not recommended to write the time zone with a ":"
               (e.g. ``+05:30``), given that the time zone is used as part of
               task output filenames.
        ''')

        with Conf('main loop'):
            with Conf('<plugin name>'):
                Conf('interval', VDR.V_INTERVAL)

        with Conf('simulation'):
            Conf('disable suite event handlers', VDR.V_BOOLEAN, True)

        with Conf('environment'):
            Conf('<variable>', VDR.V_STRING)

        with Conf('events'):
            # Note: default of None for V_STRING_LIST is used to differentiate
            # between: value not set vs value set to empty
            Conf('handlers', VDR.V_STRING_LIST, None)
            Conf('handler events', VDR.V_STRING_LIST, None)
            Conf('startup handler', VDR.V_STRING_LIST, None)
            Conf('timeout handler', VDR.V_STRING_LIST, None)
            Conf('inactivity handler', VDR.V_STRING_LIST, None)
            Conf('shutdown handler', VDR.V_STRING_LIST, None)
            Conf('aborted handler', VDR.V_STRING_LIST, None)
            Conf('stalled handler', VDR.V_STRING_LIST, None)
            Conf('timeout', VDR.V_INTERVAL)
            Conf('inactivity', VDR.V_INTERVAL)
            Conf('abort if startup handler fails', VDR.V_BOOLEAN)
            Conf('abort if shutdown handler fails', VDR.V_BOOLEAN)
            Conf('abort if timeout handler fails', VDR.V_BOOLEAN)
            Conf('abort if inactivity handler fails', VDR.V_BOOLEAN)
            Conf('abort if stalled handler fails', VDR.V_BOOLEAN)
            Conf('abort on stalled', VDR.V_BOOLEAN)
            Conf('abort on timeout', VDR.V_BOOLEAN)
            Conf('abort on inactivity', VDR.V_BOOLEAN)
            Conf('mail events', VDR.V_STRING_LIST, None)
            Conf('expected task failures', VDR.V_STRING_LIST, desc='''
                (For Cylc developers writing a functional reference test
                only) List of tasks that are expected to fail in the test.
            ''')

        with Conf('mail'):
            Conf('footer', VDR.V_STRING, desc='''
                Specify a string or string template for footers of
                emails sent for both suite and task events.

                ================ ======================
                Syntax           Description
                ================ ======================
                ``%(host)s``     Suite host name.
                ``%(port)s``     Suite port number.
                ``%(owner)s``    Suite owner name.
                ``%(suite)s``    Suite name
                ================ ======================

                Example:

                ``mail footer = see http://myhost/%(owner)s/notes/%(suite)s``

            ''')
            Conf('to', VDR.V_STRING, desc='''
                A string containing a list of addresses which can be accepted
                by the ``mail`` command.
            ''')
            Conf('from', VDR.V_STRING, desc='''
                Specify an alternative ``from`` email address for suite event
                notifications.
            ''')
            Conf('task event batch interval', VDR.V_INTERVAL, desc='''
                Gather all task event notifications in the given interval
                into a single email.

                Useful to prevent being overwhelmed by emails.
            ''')

    with Conf('task parameters', desc='''
        Define parameter values here for use in expanding
        :ref:`parameterized tasks <User Guide Param>`.
    '''):
        Conf('<parameter>', VDR.V_PARAMETER_LIST, desc='''
            Examples:
            - ``run = control, test1, test2``
            - ``mem = 1..5``  (equivalent to ``1, 2, 3, 4, 5``).
            - ``mem = -11..-7..2``  (equivalent to ``-11, -9, -7``).
        ''')
        with Conf('templates', desc='''
            Parameterized task names are expanded, for each parameter value,
            using string templates.

            You can assign templates to parameter names here to override the
            default templates.
        '''):
            Conf('<parameter>', VDR.V_STRING, desc='''
                Default for integer parameters:
                   ``_p%(p)0Nd``
                   where ``N`` is the number of digits of the maximum integer
                   value, e.g. ``foo<run>`` becomes ``foo_run3`` for ``run``
                   value ``3``.
                Default for non-integer parameters:
                    ``_%(p)s`` e.g. ``foo<run>`` becomes ``foo_top`` for
                    ``run`` value ``top``.

                Example:

                ``run = -R%(run)s`` e.g. ``foo<run>`` becomes ``foo-R3`` for
                ``run`` value ``3``.

                .. note::

                   The values of a parameter named ``p`` are substituted for
                   ``%(p)s``.  In ``_run%(run)s`` the first "run" is a string
                   literal, and the second gets substituted with each value of
                   the parameter.
            ''')

    with Conf('scheduling', desc='''
        This section allows cylc to determine when tasks are ready to run.
    '''):
        Conf('initial cycle point', VDR.V_CYCLE_POINT, desc='''
            In a cold start each cycling task (unless specifically excluded
            under :cylc:conf:`[..][special tasks]`) will be loaded into the
            suite with this cycle point, or with the closest subsequent valid
            cycle point for the task. This item can be overridden on the
            command line.

            In integer cycling, the default is ``1``.

            In date-time cycling, if you do not provide time zone information
            for this, it will be assumed to be local time, or in UTC if
            :cylc:conf:`flow.cylc[scheduler]UTC mode` is set, or in the time
            zone determined by
            :cylc:conf`flow.cylc[scheduler][cycle point time zone]`.

            The string ``now`` converts to the current date-time on the suite
            host (adjusted to UTC if the suite is in UTC mode but the host is
            not) to minute resolution.  Minutes (or hours, etc.) may be
            ignored depending on the value of

            :cylc:conf:`flow.cylc[scheduler]cycle point format`.

            For more information on setting the initial cycle point relative
            to the current time see :ref:`setting-the-icp-relative-to-now`.
        ''')
        Conf('final cycle point', VDR.V_STRING, desc='''
            Cycling tasks are held once they pass the final cycle point, if
            one is specified. Once all tasks have achieved this state the
            suite will shut down. If this item is provided you can override it
            on the command line.

            In date-time cycling, if you do not provide time zone information
            for this, it will be assumed to be local time, or in UTC if
            :cylc:conf:`flow.cylc[scheduler]UTC mode`
            is set, or in the time zone determined by
            :cylc:conf`flow.cylc[scheduler][cycle point time zone]`.
        ''')
        Conf('initial cycle point constraints', VDR.V_STRING_LIST, desc='''
            in a cycling suite it is possible to restrict the initial cycle
            point by defining a list of truncated time points under the
            initial cycle point constraints.

            Examples: T00, T06, T-30).
        ''')
        Conf('final cycle point constraints', VDR.V_STRING_LIST, desc='''
            In a cycling suite it is possible to restrict the final cycle
            point by defining a list of truncated time points under the final
            cycle point constraints.
        ''')
        Conf('hold after cycle point', VDR.V_CYCLE_POINT, desc='''
            Cycling tasks are held once they pass this cycle point, if
            specified. Unlike for the final cycle point, the suite will not
            shut down once all tasks have passed this point. If this item
            is provided you can override it on the command line.
        ''')
        Conf('stop after cycle point', VDR.V_CYCLE_POINT, desc='''
            Set stop point. Shut down after all tasks have PASSED
            this cycle point. Will be over-ridden by command line
            ``--stop-cycle-point=POINT``

            .. note:

                Not to be confused with :cylc:conf:`[..]final cycle point`:
                There can be more graph beyond this point, but you are
                choosing not to run that part of the graph.

        ''')
        Conf('cycling mode', VDR.V_STRING, Calendar.MODE_GREGORIAN,
             options=list(Calendar.MODES) + ['integer'], desc='''
            Cylc runs using the proleptic Gregorian calendar by default. This
            item allows you to either run the suite using the 360 day calendar
            (12 months of 30 days in a year) or using integer cycling. It also
            supports use of the 365 (never a leap year) and 366 (always a leap
            year) calendars.
        ''')
        Conf('runahead limit', VDR.V_STRING, 'P5', desc='''
            Runahead limiting prevents the fastest tasks in a suite from
            getting too far ahead of the slowest ones, as documented in
            :ref:`RunaheadLimit`.

            This limit on the number of consecutive spawned cycle points is
            specified by an interval between the least and most recent: either
            an integer (e.g. ``P3`` -  works for both :term:`integer cycling`
            and :term:`datetime cycling`), or a time interval (e.g. ``PT12H`` -
            only works for datetime cycling). Alternatively, if a raw number is
            given, e.g. ``7``, it will be taken to mean ``PT7H``, though this
            usage is deprecated.

            .. note::

               The integer limit format is irrespective of the labelling of
               cycle points. For example, if the runhead limit is ``P3`` and
               you have a suite *solely* consisting of a task that repeats
               "every four cycles", it would still spawn three consecutive
               cycle points at a time (starting with 1, 5 and 9). This is
               because the suite is functionally equivalent to one where the
               task repeats every cycle.

            .. note::

               The runahead limit may be automatically raised if this is
               necessary to allow a future task to be triggererd, preventing
               the suite from stalling.
        ''')

        with Conf('queues', desc='''
            Configuration of internal queues, by which the number of
            simultaneously active tasks (submitted or running) can be limited,
            per queue. By default a single queue called *default* is defined,
            with all tasks assigned to it and no limit. To use a single queue
            for the whole suite just set the limit on the *default* queue as
            required. See also :ref:`InternalQueues`.
        '''):
            with Conf('default'):
                Conf('limit', VDR.V_INTEGER, 0, desc='''
                    The maximum number of active tasks allowed at any one
                    time, for this queue.
                ''')
                Conf('members', VDR.V_STRING_LIST, desc='All tasks.''')

            with Conf('<queue name>', desc='''
                Section heading for configuration of a single queue.
            '''):
                Conf('limit', VDR.V_INTEGER, 0, desc='''
                    The maximum number of active tasks allowed at any one
                    time, for this queue.
                ''')
                Conf('members', VDR.V_STRING_LIST, desc='''
                    A list of member tasks, or task family names, to assign to
                    this queue (assigned tasks will automatically be removed
                    from the default queue).
                ''')

        with Conf('special tasks', desc='''
            This section is used to identify tasks with special behaviour.
            Family names can be used in special task lists as shorthand for
            listing all member tasks.
        '''):
            Conf('clock-trigger', VDR.V_STRING_LIST, desc='''
            .. note::

               Please read :ref:`Section External Triggers` before
               using the older clock triggers described in this section.

            Clock-trigger tasks (see :ref:`ClockTriggerTasks`) wait on a wall
            clock time specified as an offset from their own cycle point.

            Example:

               ``foo(PT1H30M), bar(PT1.5H), baz``
            ''')
            Conf('external-trigger', VDR.V_STRING_LIST, desc='''
                .. note::

                   Please read :ref:`Section External Triggers` before
                   using the older mechanism described in this section.

                Externally triggered tasks (see :ref:`Old-Style External
                Triggers`) wait on external events reported via the
                ``cylc ext-trigger`` command. To constrain triggers to a
                specific cycle point, include ``$CYLC_TASK_CYCLE_POINT``
                in the trigger message string and pass the cycle point to the
                ``cylc ext-trigger`` command.
            ''')
            Conf('clock-expire', VDR.V_STRING_LIST, desc='''
                Clock-expire tasks enter the ``expired`` state and skip job
                submission if too far behind the wall clock when they become
                ready to run.  The expiry time is specified as an offset from
                wall-clock time; typically it should be negative - see
                :ref:`ClockExpireTasks`.

                .. note::
                   The offset:

                   * May be positive or negative
                   * The offset may be omitted if it is zero.

                Example: ``PT1H`` - 1 hour
            ''')
            Conf('sequential', VDR.V_STRING_LIST, desc='''
                Sequential tasks automatically depend on their own
                previous-cycle instance.  This declaration is deprecated in
                favour of explicit inter-cycle triggers - see
                :ref:`SequentialTasks`.

                Example:
                   ``foo, bar``
            ''')

        with Conf('xtriggers', desc='''
                This section is for *External Trigger* function declarations -
                see :ref:`Section External Triggers`.
        '''):
            Conf('<xtrigger name>', VDR.V_XTRIGGER, desc='''
                Any user-defined event trigger function declarations and
                corresponding labels for use in the graph.

                See :ref:`Section External Triggers` for details.

                Example = ``my_trigger(arg1, arg2, kwarg1, kwarg2):PT10S``
            ''')

        with Conf('graph', desc='''
            The suite dependency graph is defined under this section.  You can
            plot the dependency graph as you work on it, with ``cylc graph``
            or by right clicking on the suite in the db viewer.  See also
            :ref:`User Guide Scheduling`.
        '''):
            Conf('<recurrence>', VDR.V_STRING, desc='''
                The recurrence defines the sequence of cycle points
                for which the dependency graph is valid. These should be
                specified in our ISO 8601 derived sequence syntax, or
                similar for integer cycling:

                Example Recurrences:

                date-time cycling:
                   ``T00,T06,T12,T18`` or ``PT6H`` - *every six hours*
                integer cycling:
                   ``P2`` - *every other cycle*

                See :ref:`GraphTypes` for more on recurrence expressions, and
                how multiple graphs combine.

                The value should be a dependency graph the given recurrence.
                Syntax examples follow; see also :ref:`User Guide Scheduling`
                and :ref:`TriggerTypes`.

                Example Graph Strings:

                  .. code-block:: cylc-graph

                     # baz and waz both trigger off bar
                     foo => bar => baz & waz

                     # bar triggers off foo[-P1D-PT6H]
                     foo[-P1D-PT6H] => bar

                     # faz triggers off a message output of baz
                     baz:out1 => faz

                     # Y triggers if X starts executing
                     X:start => Y

                     # Y triggers if X fails
                     X:fail => Y

                     # bar triggers if foo[-PT6H] fails
                     foo[-PT6H]:fail => bar

                     # Y suicides if X succeeds
                     X => !Y

                     # Z triggers if X succeeds or fails
                     X | X:fail => Z

                     # Z triggers if X succeeds or fails
                     X:finish => Z

                     # general conditional triggers
                     (A | B & C ) | D => foo

                     # bar triggers if foo is successfully submitted
                     foo:submit => bar

                     # bar triggers if submission of foo fails
                     foo:submit-fail => bar
            ''')

    with Conf('runtime', desc='''
        This section is used to specify how, where, and what to execute when
        tasks are ready to run. Common configuration can be factored out in a
        multiple-inheritance hierarchy of runtime namespaces that culminates
        in the tasks of the suite. Order of precedence is determined by the C3
        linearization algorithm as used to find the *method resolution order*
        in Python language class hierarchies. For details and examples see
        :ref:`User Guide Runtime`.
    '''):
        with Conf('<namespace>', desc='''
            A namespace (i.e. task or family name) or a comma-separated list
            of namespace names, and repeat as needed to define all tasks in
            the suite. Names may contain letters, digits, underscores, and
            hyphens.  A namespace represents a group or family of tasks if
            other namespaces inherit from it, or a task if no others inherit
            from it.

            Names may not contain colons (which would preclude use of
            directory paths involving the registration name in ``$PATH``
            variables). They may not contain the "." character (it will be
            interpreted as the namespace hierarchy delimiter, separating
            groups and names -huh?).

            legal values:

            - ``[foo]``
            - ``[foo, bar, baz]``

            If multiple names are listed the subsequent settings apply to
            each.

            All namespaces inherit initially from *root*, which can be
            explicitly configured to provide or override default settings for
            all tasks in the suite.
        '''):
            Conf('platform', VDR.V_STRING)
            Conf('inherit', VDR.V_STRING_LIST, desc='''
                A list of the immediate parent(s) this namespace inherits
                from. If no parents are listed ``root`` is assumed.
            ''')
            Conf('init-script', VDR.V_STRING, desc='''
                Custom script invoked by the task job script before the task
                execution environment is configured - so it does not have
                access to any suite or task environment variables. It can be
                an external command or script, or inlined scripting. The
                original intention for this item was to allow remote tasks to
                source login scripts to configure their access to cylc, but
                this should no longer be necessary.

                See also :ref:`JobScripts`.

                User-defined script items:

                * :cylc:conf:`[..]init-script`
                * :cylc:conf:`[..]env-script`
                * :cylc:conf:`[..]pre-script`
                * :cylc:conf:`[..]script`
                * :cylc:conf:`[..]post-script`
                * :cylc:conf:`[..]err-script`
                * :cylc:conf:`[..]exit-script`

                Example::

                   echo 'Hello World'
            ''')
            Conf('env-script', VDR.V_STRING, desc='''
                Custom script invoked by the task job script between the
                cylc-defined environment (suite and task identity, etc.) and
                the user-defined task runtime environment - so it has access
                to the cylc environment (and the task environment has access
                to variables defined by this scripting). It can be an
                external command or script, or inlined scripting.

                See also :ref:`JobScripts`.

                User-defined script items:

                * :cylc:conf:`[..]init-script`
                * :cylc:conf:`[..]env-script`
                * :cylc:conf:`[..]pre-script`
                * :cylc:conf:`[..]script`
                * :cylc:conf:`[..]post-script`
                * :cylc:conf:`[..]err-script`
                * :cylc:conf:`[..]exit-script`

                Example::

                   echo 'Hello World'
            ''')
            Conf('err-script', VDR.V_STRING, desc='''
                Custom script to be invoked at the end of the error trap,
                which is triggered due to failure of a command in the task job
                script or trappable job kill. The output of this will always
                be sent to STDERR and ``$1`` is set to the name of the signal
                caught by the error trap. The script should be fast and use
                very little system resource to ensure that the error trap can
                return quickly.  Companion of ``exit-script``, which is
                executed on job success.  It can be an external command or
                script, or inlined scripting.

                See also :ref:`JobScripts`.

                User-defined script items:

                * :cylc:conf:`[..]init-script`
                * :cylc:conf:`[..]env-script`
                * :cylc:conf:`[..]pre-script`
                * :cylc:conf:`[..]script`
                * :cylc:conf:`[..]post-script`
                * :cylc:conf:`[..]err-script`
                * :cylc:conf:`[..]exit-script`

                Example::

                   printenv FOO
            ''')
            Conf('exit-script', VDR.V_STRING, desc='''
                Custom script invoked at the very end of *successful* job
                execution, just before the job script exits. It should
                execute very quickly. Companion of ``err-script``, which is
                executed on job failure. It can be an external command or
                script, or inlined scripting.

                See also :ref:`JobScripts`.

                User-defined script items:

                * :cylc:conf:`[..]init-script`
                * :cylc:conf:`[..]env-script`
                * :cylc:conf:`[..]pre-script`
                * :cylc:conf:`[..]script`
                * :cylc:conf:`[..]post-script`
                * :cylc:conf:`[..]err-script`
                * :cylc:conf:`[..]exit-script`

                Example::

                   rm -f "$TMP_FILES"
            ''')
            Conf('pre-script', VDR.V_STRING, desc='''
                Custom script invoked by the task job script immediately
                before the ``script`` item (just below). It can be an
                external command or script, or inlined scripting.

                See also :ref:`JobScripts`.

                User-defined script items:

                * :cylc:conf:`[..]init-script`
                * :cylc:conf:`[..]env-script`
                * :cylc:conf:`[..]pre-script`
                * :cylc:conf:`[..]script`
                * :cylc:conf:`[..]post-script`
                * :cylc:conf:`[..]err-script`
                * :cylc:conf:`[..]exit-script`

                Example::

                   echo "Hello from suite ${CYLC_SUITE_NAME}!"
            ''')
            Conf('script', VDR.V_STRING, desc='''
                The main custom script invoked from the task job script. It
                can be an external command or script, or inlined scripting.

                See also :ref:`JobScripts`.

                User-defined script items:

                * :cylc:conf:`[..]init-script`
                * :cylc:conf:`[..]env-script`
                * :cylc:conf:`[..]pre-script`
                * :cylc:conf:`[..]script`
                * :cylc:conf:`[..]post-script`
                * :cylc:conf:`[..]err-script`
                * :cylc:conf:`[..]exit-script`

            ''')
            Conf('post-script', VDR.V_STRING, desc='''
                Custom script invoked by the task job script immediately
                after the ``script`` item (just above). It can be an external
                command or script, or inlined scripting.

                See also :ref:`JobScripts`.

                User-defined script items:

                * :cylc:conf:`[..]init-script`
                * :cylc:conf:`[..]env-script`
                * :cylc:conf:`[..]pre-script`
                * :cylc:conf:`[..]script`
                * :cylc:conf:`[..]post-script`
                * :cylc:conf:`[..]err-script`
                * :cylc:conf:`[..]exit-script`

            ''')

            Conf('work sub-directory', VDR.V_STRING, desc='''
                Task job scripts are executed from within *work directories*
                created automatically under the suite run directory. A task
                can get its own work directory from ``$CYLC_TASK_WORK_DIR``
                (or simply ``$PWD`` if it does not ``cd`` elsewhere at
                runtime). The default directory path contains task name and
                cycle point, to provide a unique workspace for every instance
                of every task. If several tasks need to exchange files and
                simply read and write from their from current working
                directory, this item can be used to override the default to
                make them all use the same workspace.

                The top level share and work directory location can be changed
                (e.g. to a large data area) by a global config setting (see
                :cylc:conf:`
                global.cylc[platforms][<platform name>]work directory`).

                .. note::

                   If you omit cycle point from the work sub-directory path
                   successive instances of the task will share the same
                   workspace. Consider the effect on cycle point offset
                   housekeeping of work directories before doing this.

                Example:

                   ``$CYLC_TASK_CYCLE_POINT/shared/``
            ''')
            Conf('execution polling intervals', VDR.V_INTERVAL_LIST, None)
            Conf('execution retry delays', VDR.V_INTERVAL_LIST, None)
            Conf('execution time limit', VDR.V_INTERVAL)
            Conf('submission polling intervals', VDR.V_INTERVAL_LIST, None)
            Conf('submission retry delays', VDR.V_INTERVAL_LIST, None)

            with Conf('meta', desc=r'''
                Section containing metadata items for this task or family
                namespace.  Several items (title, description, URL) are
                pre-defined and are used by Cylc. Others can be user-defined
                and passed to task event handlers to be interpreted according
                to your needs. For example, the value of an "importance" item
                could determine how an event handler responds to task failure
                events.

                Any suite meta item can now be passed to task event handlers
                by prefixing the string template item name with ``suite_``,
                for example:

                .. code-block:: cylc

                   [runtime]
                       [[root]]
                           [[[events]]]
                               failed handler = """
                                   send-help.sh \
                                       %(suite_title)s \
                                       %(suite_importance)s \
                                       %(title)s
                                """
            '''):
                Conf('title', VDR.V_STRING, '', desc='''
                    A single line description of this namespace. It is
                    displayed by the ``cylc list`` command and can be
                    retrieved from running tasks with the ``cylc show``
                    command.
                ''')
                Conf('description', VDR.V_STRING, '', desc='''
                    A multi-line description of this namespace, retrievable
                    from running tasks with the ``cylc show`` command.
                ''')
                Conf(
                    'URL', VDR.V_STRING, '', desc='''
                        A web URL to task documentation for this suite.  If
                        present it can be browsed with the ``cylc doc``
                        command.  The string templates ``%(suite_name)s`` and
                        ``%(task_name)s`` will be replaced with the actual
                        suite and task names.

                        See also :cylc:conf:`[meta]URL <flow.cylc[meta]URL>`.

                        Example:

                    '''
                    + '   ``http://my-site.com/suites/%(suite_name)s/'
                    + '%(task_name)s.html``')
                Conf('<custom metadata>', VDR.V_STRING, '', desc='''
                    Any user-defined metadata item.
                    These, like title, URL, etc. can be passed to task event
                    handlers to be interpreted according to your needs. For
                    example, the value of an "importance" item could determine
                    how an event handler responds to task failure events.
                ''')

            with Conf('simulation', desc='''
                Task configuration for the suite *simulation* and *dummy* run
                modes described in :ref:`SimulationMode`.
            '''):
                Conf('default run length', VDR.V_INTERVAL, DurationFloat(10),
                     desc='''
                    The default simulated job run length, if
                    ``[job]execution time limit`` and
                    ``[simulation]speedup factor`` are not set.
                ''')
                Conf('speedup factor', VDR.V_FLOAT, desc='''
                    If ``[job]execution time limit`` is set, the task
                    simulated run length is computed by dividing it by this
                    factor.

                    Example:

                       ``10.0``
                ''')
                Conf('time limit buffer', VDR.V_INTERVAL, DurationFloat(30),
                     desc='''
                    For dummy jobs, a new ``[job]execution time limit`` is set
                    to the simulated task run length plus this buffer
                    interval, to avoid job kill due to exceeding the time
                    limit.

                    Example:

                       ``PT10S``
                ''')
                Conf('fail cycle points', VDR.V_STRING_LIST, desc='''
                    Configure simulated or dummy jobs to fail at certain cycle
                    points.

                    Example:

                    - ``all`` - all instance of the task will fail
                    - ``2017-08-12T06, 2017-08-12T18`` - these instances of
                      the task will fail
                ''')
                Conf('fail try 1 only', VDR.V_BOOLEAN, True, desc='''
                    If this is set to ``True`` only the first run of the task
                    instance will fail, otherwise retries will fail too.
                ''')
                Conf('disable task event handlers', VDR.V_BOOLEAN, True,
                     desc='''
                    If this is set to ``True`` configured task event handlers
                    will not be called in simulation or dummy modes.
                ''')

            with Conf('environment filter', desc='''
                This section contains environment variable inclusion and
                exclusion lists that can be used to filter the inherited
                environment. *This is not intended as an alternative to a
                well-designed inheritance hierarchy that provides each task
                with just the variables it needs.* Filters can, however,
                improve suites with tasks that inherit a lot of environment
                they don't need, by making it clear which tasks use which
                variables.  They can optionally be used routinely as explicit
                "task environment interfaces" too, at some cost to brevity,
                because they guarantee that variables filtered out of the
                inherited task environment are not used.

                .. note::
                   Environment filtering is done after inheritance is
                   completely worked out, not at each level on the way, so
                   filter lists in higher-level namespaces only have an effect
                   if they are not overridden by descendants.
            '''):
                Conf('include', VDR.V_STRING_LIST, desc='''
                    If given, only variables named in this list will be
                    included from the inherited environment, others will be
                    filtered out. Variables may also be explicitly excluded by
                    an ``exclude`` list.
                ''')
                Conf('exclude', VDR.V_STRING_LIST, desc='''
                    Variables named in this list will be filtered out of the
                    inherited environment.  Variables may also be implicitly
                    excluded by omission from an ``include`` list.
                ''')

            with Conf('job', desc='''
                This section configures the means by which cylc submits task
                job scripts to run.
            '''):
                Conf('batch system', VDR.V_STRING)
                Conf('batch submit command template', VDR.V_STRING)

            with Conf('remote'):
                Conf('host', VDR.V_STRING)
                Conf('owner', VDR.V_STRING)
                Conf('suite definition directory', VDR.V_STRING)
                Conf('retrieve job logs', VDR.V_BOOLEAN)
                Conf('retrieve job logs max size', VDR.V_STRING)
                Conf('retrieve job logs retry delays',
                     VDR.V_INTERVAL_LIST, None)

            with Conf('events', desc='''
                Cylc can call nominated event handlers when certain task
                events occur. This section configures specific task event
                handlers; see :cylc:conf:`flow.cylc[scheduler][events]` for
                suite event handlers.

                Event handlers can be located in the suite ``bin/`` directory,
                otherwise it is up to you to ensure their location is in
                ``$PATH`` (in the shell in which the suite server program
                runs). They should require little resource to run and return
                quickly.

                Each task event handler can be specified as a list of command
                lines or command line templates. They can contain any or all
                of the following patterns, which will be substituted with
                actual values:

                ``%(event)s``
                   Event name
                ``%(suite)s``
                   Suite name
                ``%(suite_uuid)s``
                   Suite UUID string
                ``%(point)s``
                   Cycle point
                ``%(name)s``
                   Task name
                ``%(submit_num)s``
                   Submit number
                ``%(try_num)s``
                   Try number
                ``%(id)s``
                   Task ID (i.e. %(name)s.%(point)s)
                ``%(job_runner_name)s``
                   Job runner name (previously ``%(batch_sys_name)s``)
                ``%(job_id)s``
                   Job ID in the job runner
                   (previously ``%(batch_sys_job_id)s``)
                ``%(submit_time)s``
                   Date-time when task job is submitted
                ``%(start_time)s``
                   Date-time when task job starts running
                ``%(finish_time)s``
                   Date-time when task job exits
                ``%(platform_name)s``
                   name of platform where the task job is submitted
                ``%(message)s``
                   Event message, if any
                any task [meta] item, e.g.:
                   ``%(title)s``
                      Task title
                   ``%(URL)s``
                      Task URL
                   ``%(importance)s``
                      Example custom task metadata
                any suite ``[meta]`` item, prefixed with ``suite_``
                   ``%(suite_title)s``
                      Suite title
                   ``%(suite_URL)s``
                      Suite URL.
                   ``%(suite_rating)s``
                      Example custom suite metadata.

                Otherwise, the command line will be called with the following
                default

                Arguments:

                .. code-block:: none

                   <task-event-handler> %(event)s %(suite)s %(id)s %(message)s

                .. note::

                   Substitution patterns should not be quoted in the template
                   strings.  This is done automatically where required.

                For an explanation of the substitution syntax, see
                `String Formatting Operations in the Python
                documentation
                <https://docs.python.org/3/library/stdtypes.html
                #printf-style-string-formatting>`_.

                Additional variables can be passed to event handlers using
                :ref:`Jinja2 <User Guide Jinja2>`.
                .
            '''):
                Conf('execution timeout', VDR.V_INTERVAL, desc='''
                    If a task has not finished after the specified ISO 8601
                    duration/interval, the *execution timeout* event
                    handler(s) will be called.
                ''')
                Conf('handlers', VDR.V_STRING_LIST, None, desc='''
                    Specify a list of command lines or command line templates
                    as task event handlers.
                ''')
                Conf('handler events', VDR.V_STRING_LIST, None, desc='''
                    Specify the events for which the general task event
                    handlers should be invoked.

                    Example:

                       ``submission failed, failed``
                ''')
                Conf('handler retry delays', VDR.V_INTERVAL_LIST, None,
                     desc='''
                    Specify an initial delay before running an event handler
                    command and any retry delays in case the command returns a
                    non-zero code. The default behaviour is to run an event
                    handler command once without any delay.

                    Example:

                       ``PT10S, PT1M, PT5M``
                ''')
                Conf('mail events', VDR.V_STRING_LIST, None, desc='''
                    Specify the events for which notification emails should be
                    sent.

                    Example:

                       ``submission failed, failed``
                ''')
                Conf('submission timeout', VDR.V_INTERVAL, desc='''
                    If a task has not started after the specified ISO 8601
                    duration/interval, the *submission timeout* event
                    handler(s) will be called.
                ''')
                Conf('expired handler', VDR.V_STRING_LIST, None)
                Conf('late offset', VDR.V_INTERVAL, None)
                Conf('late handler', VDR.V_STRING_LIST, None)
                Conf('submitted handler', VDR.V_STRING_LIST, None)
                Conf('started handler', VDR.V_STRING_LIST, None)
                Conf('succeeded handler', VDR.V_STRING_LIST, None)
                Conf('failed handler', VDR.V_STRING_LIST, None)
                Conf('submission failed handler', VDR.V_STRING_LIST, None)
                Conf('warning handler', VDR.V_STRING_LIST, None)
                Conf('critical handler', VDR.V_STRING_LIST, None)
                Conf('retry handler', VDR.V_STRING_LIST, None)
                Conf('submission retry handler', VDR.V_STRING_LIST, None)
                Conf('execution timeout handler', VDR.V_STRING_LIST, None)
                Conf('submission timeout handler', VDR.V_STRING_LIST, None)
                Conf('custom handler', VDR.V_STRING_LIST, None)

            with Conf('mail', desc='''
                Settings for mail events.
            '''):
                Conf('from', VDR.V_STRING, desc='''
                    Specify an alternate ``from:`` email address for event
                    notifications.
                ''')
                Conf('to', VDR.V_STRING, desc='''
                    A list of email addresses to send task event
                    notifications. The list can be anything accepted by the
                    ``mail`` command.
                ''')

            with Conf('suite state polling', desc='''
                Configure automatic suite polling tasks as described in
                :ref:`SuiteStatePolling`. The items in this section reflect
                the options and defaults of the ``cylc suite-state`` command,
                except that the target suite name and the
                ``--task``, ``--cycle``, and ``--status`` options are
                taken from the graph notation.
            '''):
                Conf('user', VDR.V_STRING, desc='''
                    Username of an account on the suite host to which you have
                    access. The polling ``cylc suite-state`` command will be
                    invoked on the remote account.
                ''')
                Conf('host', VDR.V_STRING, desc='''
                    The hostname of the target suite. The polling
                    ``cylc suite-state`` command will be invoked on the remote
                    account.
                ''')
                Conf('interval', VDR.V_INTERVAL, desc='''
                    Polling interval expressed as an ISO 8601
                    duration/interval.
                ''')
                Conf('max-polls', VDR.V_INTEGER, desc='''
                    The maximum number of polls before timing out and entering
                    the "failed" state.
                ''')
                Conf('message', VDR.V_STRING, desc='''
                    Wait for the target task in the target suite to receive a
                    specified message rather than achieve a state.
                ''')
                Conf('run-dir', VDR.V_STRING, desc='''
                    For your own suites the run database location is
                    determined by your site/user config. For other suites,
                    e.g. those owned by others, or mirrored suite databases,
                    use this item to specify the location of the top level
                    cylc run directory (the database should be a suite-name
                    sub-directory of this location).
                ''')
                Conf('verbose mode', VDR.V_BOOLEAN, desc='''
                    Run the polling ``cylc suite-state`` command in verbose
                    output mode.
                ''')

            with Conf('environment', desc='''
                The user defined task execution environment. Variables
                defined here can refer to cylc suite and task identity
                variables, which are exported earlier in the task job
                script, and variable assignment expressions can use cylc
                utility commands because access to cylc is also configured
                earlier in the script.  See also
                :ref:`TaskExecutionEnvironment`.

                You can also specify job environment templates here for
                :ref:`parameterized tasks <User Guide Param>`.
            '''):
                Conf('<variable>', VDR.V_STRING, desc='''
                    The order of definition is
                    preserved so values can refer to previously defined
                    variables. Values are passed through to the task job
                    script without evaluation or manipulation by Cylc
                    (with the exception of valid Python string templates
                    that match parameterized task names - see below), so any
                    variable assignment expression that is legal in the job
                    submission shell can be used.  White space around the
                    ``=`` is allowed (as far as cylc's flow.cylc parser is
                    concerned these are just normal configuration items).

                    Examples::

                       FOO = $HOME/bar/baz
                       BAR = ${FOO}$GLOBALVAR
                       BAZ = $( echo "hello world" )
                       WAZ = ${FOO%.jpg}.png
                       NEXT_CYCLE = $( cylc cycle-point --offset=PT6H )
                       ZAZ = "${FOO#bar}"
                       # ^ quoted to escape the flow.cylc comment character

                    For parameter environment templates, use Python string
                    templates for parameter substitution. This is only
                    relevant for
                    :ref:`parameterized tasks <User Guide Param>`.
                    The job script will export the named variables specified
                    here (in addition to the standard ``CYLC_TASK_PARAM_<key>``
                    variables), with the template strings substituted with
                    the parameter values.

                    Examples::

                       MYNUM = %(i)d
                       MYITEM = %(item)s
                       MYFILE = /path/to/%(i)03d/%(item)s
                ''')

            with Conf('directives', desc='''
                Batch queue scheduler directives.  Whether or not these are
                used depends on the batch system/job runner. For the built-in
                methods  support directives (``loadleveler``, ``lsf``,
                ``pbs``, ``sge``, ``slurm``, ``slurm_packjob``, ``moab``),
                directives  written to the
                top of the task job script in the correct format for the
                method. Specifying directives individually like this allows
                use of default directives that can be individually overridden
                at lower levels of the runtime namespace hierarchy.
            '''):
                Conf('<directive>', VDR.V_STRING, desc='''
                    e.g. ``class = parallel``.

                    Example directives for the built-in job runner handlers
                    are shown in :ref:`AvailableMethods`.
                ''')

            with Conf('outputs', desc='''
                Register custom task outputs for use in message triggering in
                this section (:ref:`MessageTriggers`)
            '''):
                Conf('<output>', VDR.V_STRING, desc='''
                    Task output messages (:ref:`MessageTriggers`). The
                    item name is used to select the custom output
                    message in graph trigger notation.

                    Examples:

                    .. code-block:: cylc

                       out1 = "sea state products ready"
                       out2 = "NWP restart files completed"

                    Task outputs are validated by
                    :py:class:`cylc.flow.unicode_rules.TaskOutputValidator`.

                    .. autoclass:: cylc.flow.unicode_rules.TaskOutputValidator
                ''')

            with Conf('parameter environment templates', desc='''
                .. note::

                   This section is deprecated and will be removed in Cylc 9.
                   Parameter environment templates have moved to
                   :cylc:conf:`flow.cylc[runtime][<namespace>][environment]`.
                   This was done to allow users to control the order of
                   definition of the variables.

                   For the time being, the contents of this section will be
                   prepended to the ``[environment]`` section when running
                   a suite.
            '''):
                Conf('<parameter>', VDR.V_STRING)

    with Conf('visualization'):
        Conf('initial cycle point', VDR.V_CYCLE_POINT)
        Conf('final cycle point', VDR.V_STRING)
        Conf('number of cycle points', VDR.V_INTEGER, 3)
        Conf('collapsed families', VDR.V_STRING_LIST)
        Conf('use node color for edges', VDR.V_BOOLEAN)
        Conf('use node fillcolor for edges', VDR.V_BOOLEAN)
        Conf('use node color for labels', VDR.V_BOOLEAN)
        Conf('node penwidth', VDR.V_INTEGER, 2)
        Conf('edge penwidth', VDR.V_INTEGER, 2)
        Conf('default node attributes', VDR.V_STRING_LIST,
             default=['style=unfilled', 'shape=ellipse'])
        Conf('default edge attributes', VDR.V_STRING_LIST)

        with Conf('node groups'):
            Conf('<group>', VDR.V_STRING_LIST)

        with Conf('node attributes'):
            Conf('<node>', VDR.V_STRING_LIST)


def upg(cfg, descr):
    """Upgrade old suite configuration."""
    u = upgrader(cfg, descr)
    u.obsolete(
        '7.8.0',
        ['runtime', '__MANY__', 'suite state polling', 'template'])
    u.obsolete('7.8.1', ['cylc', 'events', 'reset timer'])
    u.obsolete('7.8.1', ['cylc', 'events', 'reset inactivity timer'])
    u.obsolete('8.0.0', ['cylc', 'force run mode'])
    u.obsolete('7.8.1', ['runtime', '__MANY__', 'events', 'reset timer'])
    u.obsolete('8.0.0', ['cylc', 'authentication'])
    u.obsolete('8.0.0', ['cylc', 'include at start-up'])
    u.obsolete('8.0.0', ['cylc', 'exclude at start-up'])
    u.obsolete('8.0.0', ['cylc', 'log resolved dependencies'])
    u.obsolete('8.0.0', ['cylc', 'required run mode'])
    u.obsolete(
        '8.0.0',
        ['cylc', 'health check interval'])
    u.obsolete('8.0.0', ['runtime', '__MANY__', 'events', 'mail retry delays'])
    u.obsolete('8.0.0', ['runtime', '__MANY__', 'extra log files'])
    u.obsolete('8.0.0', ['runtime', '__MANY__', 'job', 'shell'])
    u.obsolete('8.0.0', ['cylc', 'abort if any task fails'])
    u.obsolete('8.0.0', ['cylc', 'events', 'abort if any task fails'])
    u.obsolete('8.0.0', ['cylc', 'events', 'mail retry delays'])
    u.obsolete('8.0.0', ['cylc', 'disable automatic shutdown'])
    u.obsolete('8.0.0', ['cylc', 'environment'])
    u.obsolete('8.0.0', ['cylc', 'reference test'])
    u.obsolete('8.0.0', ['cylc', 'simulation', 'disable suite event handlers'])
    u.obsolete('8.0.0', ['cylc', 'simulation'])
    u.deprecate(
        '8.0.0',
        ['cylc', 'task event mail interval'],
        ['cylc', 'mail', 'task event batch interval']
    )
    u.deprecate('8.0.0', ['cylc', 'parameters'], ['task parameters'])
    u.deprecate(
        '8.0.0',
        ['cylc', 'parameter templates'],
        ['task parameters', 'templates']
    )
    # Whole workflow task mail settings
    for mail_setting in ['to', 'from', 'footer']:
        u.deprecate(
            '8.0.0',
            ['cylc', 'events', f'mail {mail_setting}'],
            ['cylc', 'mail', mail_setting]
        )
    # Task mail settings in [runtime][TASK]
    for mail_setting in ['to', 'from']:
        u.deprecate(
            '8.0.0',
            ['runtime', '__MANY__', 'events', f'mail {mail_setting}'],
            ['runtime', '__MANY__', 'mail', mail_setting]
        )
    u.deprecate(
        '8.0.0',
        ['cylc', 'events', 'mail smtp'],
        None,  # This is really a .obsolete(), just with a custom message
        cvtr=converter(lambda x: x, (
            'DELETED (OBSOLETE) - use "global.cylc[scheduler][mail]smtp" '
            'instead'))
    )
    u.deprecate(
        '8.0.0',
        ['runtime', '__MANY__', 'events', 'mail smtp'],
        None,
        cvtr=converter(lambda x: x, (
            'DELETED (OBSOLETE) - use "global.cylc[scheduler][mail]smtp" '
            'instead'))
    )
    u.deprecate(
        '8.0.0',
        ['scheduling', 'max active cycle points'],
        ['scheduling', 'runahead limit'],
        cvtr=converter(lambda x: f'P{x}' if x != '' else '', '"n" -> "Pn"')
    )
    u.deprecate(
        '8.0.0',
        ['scheduling', 'hold after point'],
        ['scheduling', 'hold after cycle point']
    )

    for job_setting in [
        'execution polling intervals',
        'execution retry delays',
        'execution time limit',
        'submission polling intervals',
        'submission retry delays'
    ]:
        u.deprecate(
            '8.0.0',
            ['runtime', '__MANY__', 'job', job_setting],
            ['runtime', '__MANY__', job_setting]
        )

    u.deprecate('8.0.0', ['cylc'], ['scheduler'])
    u.upgrade()

    upgrade_graph_section(cfg, descr)
    upgrade_param_env_templates(cfg, descr)

    warn_about_depr_platform(cfg)
    warn_about_depr_event_handler_tmpl(cfg)


def upgrade_graph_section(cfg, descr):
    """Upgrade Cylc 7 `[scheduling][dependencies][X]graph` format to
    `[scheduling][graph]X`."""
    # Parsec upgrader cannot do this type of move
    try:
        if 'dependencies' in cfg['scheduling']:
            msg_old = '[scheduling][dependencies][X]graph'
            msg_new = '[scheduling][graph]X'
            if 'graph' in cfg['scheduling']:
                raise UpgradeError(
                    f'Cannot upgrade deprecated item "{msg_old} -> {msg_new}" '
                    f'because {msg_new[:-1]} already exists.'
                )
            else:
                keys = set()
                cfg['scheduling'].setdefault('graph', {})
                cfg['scheduling']['graph'].update(
                    cfg['scheduling'].pop('dependencies')
                )
                graphdict = cfg['scheduling']['graph']
                for key, value in graphdict.copy().items():
                    if isinstance(value, dict) and 'graph' in value:
                        graphdict[key] = value['graph']
                        keys.add(key)
                if keys:
                    keys = ', '.join(sorted(keys))
                    LOG.warning(
                        'deprecated graph items were automatically upgraded '
                        f'in "{descr}":\n'
                        f' * (8.0.0) {msg_old} -> {msg_new} - for X in:\n'
                        f'       {keys}'
                    )
    except KeyError:
        pass


def upgrade_param_env_templates(cfg, descr):
    """Prepend contents of `[runtime][X][parameter environment templates]` to
    `[runtime][X][environment]`."""

    if 'runtime' in cfg:
        dep = '[runtime][%s][parameter environment templates]'
        new = '[runtime][%s][environment]'
        first_warn = True
        for task_name, task_items in cfg['runtime'].items():
            if 'parameter environment templates' not in task_items:
                continue
            if first_warn is True:
                LOG.warning(
                    f'deprecated items automatically upgraded in "{descr}":'
                )
                first_warn = False
            LOG.warning(
                f' * (8.0.0) {dep % task_name} contents prepended to '
                f'{new % task_name}'
            )
            for key, val in reversed(
                    task_items['parameter environment templates'].items()):
                if 'environment' in task_items:
                    if key in task_items['environment']:
                        LOG.warning(
                            f' *** {dep % task_name} {key} ignored as {key} '
                            f'already exists in {new % task_name}'
                        )
                        continue
                else:
                    task_items['environment'] = OrderedDictWithDefaults()
                task_items['environment'].prepend(key, val)
            task_items.pop('parameter environment templates')


def warn_about_depr_platform(cfg):
    """Warn if deprecated host or batch system appear in config."""
    if 'runtime' in cfg:
        for task_name, task_cfg in cfg['runtime'].items():
            platform = get_platform(task_cfg, task_name, warn_only=True)
            if type(platform) == str:
                LOG.warning(platform)


def warn_about_depr_event_handler_tmpl(cfg):
    """Warn if deprecated template strings appear in event handlers."""
    if 'runtime' not in cfg:
        return
    deprecation_msg = (
        'The event handler template variable "%({0})s" is deprecated - '
        'use "%({1})s" instead.')
    for task in cfg['runtime']:
        if 'events' not in cfg['runtime'][task]:
            continue
        for event, handler in cfg['runtime'][task]['events'].items():
            if f'%({EventData.JobID_old.value})' in handler:
                LOG.warning(
                    deprecation_msg.format(EventData.JobID_old.value,
                                           EventData.JobID.value)
                )
            if f'%({EventData.JobRunnerName_old.value})' in handler:
                LOG.warning(
                    deprecation_msg.format(EventData.JobRunnerName_old.value,
                                           EventData.JobRunnerName.value)
                )


class RawSuiteConfig(ParsecConfig):
    """Raw suite configuration."""

    def __init__(self, fpath, output_fname, tvars):
        """Return the default instance."""
        ParsecConfig.__init__(
            self, SPEC, upg, output_fname, tvars, cylc_config_validate)
        self.loadcfg(fpath, "suite definition")
