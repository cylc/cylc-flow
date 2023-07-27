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
"""Define all legal items and values for cylc workflow definition files."""

import contextlib
import re
from textwrap import dedent
from typing import Any, Dict, Optional, Set

from metomi.isodatetime.data import Calendar

from cylc.flow import LOG
from cylc.flow.cfgspec.globalcfg import (
    DIRECTIVES_DESCR,
    DIRECTIVES_ITEM_DESCR,
    LOG_RETR_SETTINGS,
    EVENTS_DESCR,
    EVENTS_SETTINGS,
    EXECUTION_POLL_DESCR,
    MAIL_DESCR,
    MAIL_FOOTER_DESCR,
    MAIL_FROM_DESCR,
    MAIL_INTERVAL_DESCR,
    MAIL_TO_DESCR,
    MAIN_LOOP_DESCR,
    MAIN_LOOP_PLUGIN_DESCR,
    MAIN_LOOP_PLUGIN_INTERVAL_DESCR,
    REPLACES,
    SCHEDULER_DESCR,
    SUBMISSION_POLL_DESCR,
    SUBMISSION_RETY_DESCR,
    TASK_EVENTS_DESCR,
    TASK_EVENTS_SETTINGS,
    UTC_MODE_DESCR,
)
import cylc.flow.flags
from cylc.flow.parsec.exceptions import UpgradeError
from cylc.flow.parsec.config import ParsecConfig, ConfigNode as Conf
from cylc.flow.parsec.OrderedDict import OrderedDictWithDefaults
from cylc.flow.parsec.upgrade import upgrader, converter
from cylc.flow.parsec.validate import (
    DurationFloat, CylcConfigValidator as VDR, cylc_config_validate)
from cylc.flow.platforms import (
    fail_if_platform_and_host_conflict, get_platform_deprecated_settings,
    is_platform_definition_subshell)
from cylc.flow.task_events_mgr import EventData

# Regex to check whether a string is a command
REC_COMMAND = re.compile(r'(`|\$\()\s*(.*)\s*([`)])$')

REPLACED_BY_PLATFORMS = '''
.. deprecated:: 8.0.0

   This is used to select a matching platform.
   It will be removed in a future version of Cylc 8.
   Please set a suitable platform in
   :cylc:conf:`flow.cylc[runtime][<namespace>]platform` instead.
   :ref:`See the migration guide <MajorChangesPlatforms>`.
'''


def global_default(text: str, config_path: str) -> str:
    """Insert a link to this config item's global counterpart after the first
    paragraph of the description text. Also dedents.
    """
    first, sep, rest = dedent(text).partition('\n\n')
    return (
        f"{first}\n\n"
        "The default value is set in the global config: "
        f":cylc:conf:`global.cylc{config_path}`."
        f"{sep}{rest}"
    )


def get_script_common_text(this: str, example: Optional[str] = None):
    text = dedent('''

    See also :ref:`JobScripts`.

    Other user-defined script items:

    ''')
    for item in (
        'init-script', 'env-script', 'pre-script', 'script', 'post-script',
        'err-script', 'exit-script'
    ):
        if item != this:
            text += f"* :cylc:conf:`[..]{item}`\n"
    text += dedent(f'''

    Example::

       {example if example else 'echo "Hello World"'}
    ''')
    return text


with Conf(
    'flow.cylc',
    desc='''
        Defines a Cylc workflow configuration.

        After processing any embedded templating code
        (see :ref:`Jinja`) the resultant raw flow.cylc file
        must be valid. See also :ref:`FlowConfigFile` for a descriptive
        overview of flow.cylc files, including syntax (:ref:`Syntax`).

        .. versionchanged:: 8.0.0

           The configuration file was previously named ``suite.rc``, but that
           name is now deprecated.
           The ``suite.rc`` file name now activates :ref:`cylc_7_compat_mode`.
           Rename to ``flow.cylc`` to turn off compatibility mode.
    '''
) as SPEC:

    with Conf('meta', desc='''
        Metadata for this workflow.

        Cylc defines and uses
        the terms "title", "description" and "URL".
        Users can define more terms, and use these in event handlers.

        Example::

           A user could define "workflow-priority". An event handler
           would then respond to failure events in a way set by
           "workflow-priority".
    '''):
        Conf('description', VDR.V_STRING, '', desc='''
            A multi-line description of the workflow.

            It can be retrieved at run time with the ``cylc show`` command.
        ''')
        Conf('title', VDR.V_STRING, '', desc='''
            A single line description of the workflow.

            It can be retrieved at run time with the ``cylc show`` command.
        ''')
        Conf('URL', VDR.V_STRING, '', desc='''
            A web URL to workflow documentation.

            The URL can be retrieved at run time with the ``cylc show``
            command.

            The template variable ``%(workflow)s`` will be replaced with the
            actual workflow ID.

            .. deprecated:: 8.0.0

               The ``%(suite_name)s`` template variable is deprecated, please
               use ``%(workflow)s``.

            .. seealso::

               :cylc:conf:`flow.cylc[runtime][<namespace>][meta]URL`.

            Example:

            ``http://my-site.com/workflows/%(workflow)s/index.html``

        ''')
        Conf('<custom metadata>', VDR.V_STRING, '', desc='''
            Any user-defined metadata item.

            Like title, description and URL these can be
            passed to workflow event handlers to be interpreted according to
            your needs.

            For example, a user could define an item called
            "workflow-priority". An event handler could then respond to
            failure events in a way set by "workflow-priority".
        ''')
    with Conf('scheduler', desc=(
        global_default(SCHEDULER_DESCR, "[scheduler]")
    )):
        Conf('UTC mode', VDR.V_BOOLEAN, desc=(
            global_default(UTC_MODE_DESCR, "[scheduler]UTC mode")
        ))

        Conf('allow implicit tasks', VDR.V_BOOLEAN, default=False, desc='''
            Allow tasks in the graph that are not defined in
            :cylc:conf:`flow.cylc[runtime]`.

            :term:`Implicit tasks <implicit task>` are tasks without explicit
            definitions in :cylc:conf:`flow.cylc[runtime]`. By default,
            these are not allowed, as they are often typos. However,
            this setting can be set to ``True`` to allow implicit tasks.
            It is recommended to only set this to ``True`` if required during
            development/prototyping of a workflow graph, but set it to
            ``False`` after finishing the :cylc:conf:`flow.cylc[runtime]`
            section.

            .. admonition:: Cylc 7 compatibility mode

               In :ref:`Cylc_7_compat_mode`, implicit tasks are still
               allowed unless you explicitly set this to ``False``, or
               unless a ``rose-suite.conf`` file is present (to maintain
               backward compatibility with Rose 2019).

            .. versionadded:: 8.0.0
        ''')

        Conf('install', VDR.V_STRING_LIST, desc='''
            Configure custom directories and files to be installed on remote
            hosts.

            .. note::

               The following directories already get installed by default:

               ``ana/``
                  Rose ana analysis modules
               ``app/``
                  Rose applications
               ``bin/``
                  Cylc bin directory (added to ``PATH``)
               ``etc/``
                  Miscellaneous resources
               ``lib/``
                  Cylc lib directory (``lib/python`` added to ``PYTHONPATH``
                  for workflow config)

               These should be located in the top level of your Cylc workflow,
               i.e. the directory that contains your ``flow.cylc`` file.

            Directories must have a trailing slash.
            For example, to add the following items to your file installation:

            .. code-block:: none

                ~/cylc-run/workflow_x
                |-- dir1/
                |-- dir2/
                |-- file1
                `-- file2

            .. code-block:: cylc

                [scheduler]
                    install = dir/, dir2/, file1, file2

            .. versionadded:: 8.0.0
        ''')

        Conf('cycle point format', VDR.V_CYCLE_POINT_FORMAT, desc='''
            Set the datetime format and precision that Cylc uses for
            :term:`cycle points<cycle point>` in :term:`datetime cycling`
            workflows.

            .. seealso::

               * To alter the time zone used in the datetime cycle point
                 format, see
                 :cylc:conf:`flow.cylc[scheduler]cycle point time zone`.
               * To alter the number of expanded year digits (for years
                 below 0 or above 9999), see
                 :cylc:conf:`flow.cylc
                 [scheduler]cycle point num expanded year digits`.

            By default, Cylc uses a ``CCYYMMDDThhmmZ`` (``Z`` in the special
            case of UTC) or ``CCYYMMDDThhmm±hhmm`` format for writing
            datetime cycle points, following the :term:`ISO 8601` standard.

            You may use the `isodatetime library's syntax
            <https://github.com/metomi/isodatetime#dates-and-times>`_ to set
            the cycle point format.

            You can also use a subset of the strptime/strftime POSIX
            standard - supported tokens are ``%F``, ``%H``, ``%M``, ``%S``,
            ``%Y``, ``%d``, ``%j``, ``%m``, ``%s``, ``%z``.

            If specifying a format here, we recommend including a time zone -
            this will be used for displaying cycle points only. To avoid
            confusion, we recommend using the same time zone as
            :cylc:conf:`flow.cylc[scheduler]cycle point time zone`.

            The ISO 8601 *extended* datetime format (``CCYY-MM-DDThh:mm``)
            cannot be used, as cycle points are used in job-log and work
            directory paths where the ":" character is invalid.

            .. warning::

               The smallest unit included in the format sets the precision
               of cycle points in the workflow.
               If the precision is lower than the smallest unit
               in a graph recurrence, the workflow will fail.
               For example, if you set a format of ``CCYY``, and have a
               recurrence ``R/2000/P8M``, then both the first and second
               cycle points will be ``2000``, which is invalid.
        ''')
        Conf('cycle point num expanded year digits', VDR.V_INTEGER, 0, desc='''
            Enable negative years or years more than four digits long.

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
            Time zone to be used for datetime cycle points if not otherwise
            specified.

            This time zone will be used for
            datetime cycle point dumping and inferring the time zone of cycle
            points that are input without time zones.

            Time zones should be expressed as :term:`ISO8601` time zone offsets
            from UTC, such as ``+13``, ``+1300``, ``-0500`` or ``+0645``,
            with ``Z`` representing the special case of ``+0000`` (UTC).
            Cycle points will be converted to the time zone you give and will
            be represented with this string at the end.

            If not set, it will default to UTC (``Z``).

            .. admonition:: Cylc 7 compatibility mode

               In :ref:`Cylc_7_compat_mode`, it will default to the
               local/system time zone, rather than UTC.

            The time zone will persist over reloads/restarts following any
            local time zone changes (e.g. if the
            workflow is run during winter time, then stopped, then restarted
            after summer time has begun, the cycle points will remain
            in winter time). Changing this setting after the workflow has
            first started will have no effect.

            If you use a custom
            :cylc:conf:`flow.cylc[scheduler]cycle point format`, it is a good
            idea to set the same time zone here. If you specify a different
            one here, it will only be used for inferring timezone-less cycle
            points; cycle points will be displayed in the time zone from the
            cycle point format.

            .. caution::

               It is not recommended to write the time zone with a ":"
               (e.g. ``+05:30``), given that the time zone is used as part of
               task output filenames.

            .. seealso::

               :cylc:conf:`flow.cylc[scheduler]UTC mode`

            .. versionchanged:: 7.8.9/7.9.4

               The value set here now persists over reloads/restarts after a
               system time zone change.

            .. versionchanged:: 8.0.0

               The default time zone is now ``Z`` instead of the local time of
               the first workflow start.
        ''')

        with Conf(   # noqa: SIM117 (keep same format)
            'main loop',
            desc=global_default(MAIN_LOOP_DESCR, "[scheduler][main loop]")
        ):
            with Conf('<plugin name>', desc=(
                global_default(
                    MAIN_LOOP_PLUGIN_DESCR,
                    "[scheduler][main loop][<plugin name>]"
                )
            )):
                Conf('interval', VDR.V_INTERVAL, desc=(
                    global_default(
                        MAIN_LOOP_PLUGIN_INTERVAL_DESCR,
                        "[scheduler][main loop][<plugin name>]interval"
                    )
                ))

        with Conf('events',
                  desc=global_default(EVENTS_DESCR, '[scheduler][events]')):
            for item, desc in EVENTS_SETTINGS.items():
                desc = global_default(desc, f"[scheduler][events]{item}")
                vdr_type = VDR.V_STRING_LIST
                default: Any = Conf.UNSET
                if item in {'handlers', 'handler events', 'mail events'}:
                    # Note: default of None for V_STRING_LIST is used to
                    # differentiate between not set vs set to empty
                    default = None
                elif item.endswith("handlers"):
                    desc = desc + '\n\n' + dedent(rf'''
                        Examples:

                        .. code-block:: cylc

                           # configure a single event handler
                           {item} = echo foo

                           # provide context to the handler
                           {item} = echo %(workflow)s

                           # configure multiple event handlers
                           {item} = \
                               'echo %(workflow)s, %(event)s', \
                               'my_exe %(event)s %(message)s' \
                               'curl -X PUT -d event=%(event)s host:port'
                    ''')
                elif item.startswith("abort on"):
                    vdr_type = VDR.V_BOOLEAN
                elif item.endswith("timeout"):
                    vdr_type = VDR.V_INTERVAL
                Conf(item, vdr_type, default, desc=desc)

            Conf('expected task failures', VDR.V_STRING_LIST, desc='''
                (For Cylc developers writing a functional tests only)
                List of tasks that are expected to fail in the test.
            ''')

        with Conf('mail', desc=(
            global_default(MAIL_DESCR, "[scheduler][mail]")
        )):
            Conf('footer', VDR.V_STRING, desc=(
                global_default(MAIL_FOOTER_DESCR, "[scheduler][mail]footer")
            ))
            Conf('to', VDR.V_STRING, desc=(
                global_default(MAIL_TO_DESCR, "[scheduler][mail]to")
            ))
            Conf('from', VDR.V_STRING, desc=(
                global_default(MAIL_FROM_DESCR, "[scheduler][mail]from")
            ))
            Conf('task event batch interval', VDR.V_INTERVAL, desc=(
                global_default(
                    MAIL_INTERVAL_DESCR,
                    "[scheduler][mail]task event batch interval"
                )
            ))

    with Conf('task parameters', desc=f'''
        Set task parameters and parameter templates.

        Define parameter values here for use in expanding
        :ref:`parameterized tasks <User Guide Param>`.

        .. versionchanged:: 8.0.0

           {REPLACES}``[cylc][parameters]``.
    '''):
        Conf('<parameter>', VDR.V_PARAMETER_LIST, desc='''
            A custom parameter to use in a workflow.

            Examples:

            - ``run = control, test1, test2``
            - ``mem = 1..5``  (equivalent to ``1, 2, 3, 4, 5``).
            - ``mem = -11..-7..2``  (equivalent to ``-11, -9, -7``).
        ''')
        with Conf('templates', desc=f'''
            Cylc will expand each parameterized task name using a string
            template.

            You can set templates for any parameter name here to override the
            default template.

            .. versionchanged:: 8.0.0

               {REPLACES}``[cylc][parameter templates]``.
        '''):
            Conf('<parameter>', VDR.V_STRING, desc='''
                A template for a parameter.

                For example:

                If you set:

                .. code-block:: cylc

                   [task parameters]
                       myparameter = 1..3
                       [[templates]]
                           myparameter = _run_%(myparameter)s

                task name ``foo<myparameter>`` becomes ``foo_run_3`` for
                ``run == 3``.

                .. note::

                   The default parameter templates are:

                   For integer parameters:
                      ``_p%(p)0Nd``
                      where ``N`` is the number of digits of the maximum
                      integer value, i.e. If the largest parameter value is
                      3142 then N = 4.

                   Default for non-integer parameters:
                      ``_%(p)s`` e.g. ``foo<run>`` becomes ``foo_top`` for
                      ``run`` value ``top``.
            ''')

    with Conf('scheduling', desc='''
        This section allows Cylc to determine when tasks are ready to run.

        Any cycle points defined here without a time zone will use the
        time zone from
        :cylc:conf:`flow.cylc[scheduler]cycle point time zone`.
    '''):
        Conf('initial cycle point', VDR.V_CYCLE_POINT, desc='''
            The earliest cycle point at which any task can run.

            In a cold start each cycling task (unless specifically excluded
            under :cylc:conf:`[..][special tasks]`) will be loaded into the
            workflow with this cycle point, or with the closest subsequent
            valid cycle point for the task.

            In integer cycling, the default is ``1``.

            The string ``now`` converts to the current datetime on the workflow
            host when first starting the workflow (with precision determined
            by :cylc:conf:`flow.cylc[scheduler]cycle point format`).

            For more information on setting the initial cycle point relative
            to the current time see :ref:`setting-the-icp-relative-to-now`.

            This item can be overridden on the command line using
            ``cylc play --initial-cycle-point`` or ``--icp``.
        ''')
        # NOTE: final cycle point is not a V_CYCLE_POINT to allow expressions
        # such as '+P1Y' (relative to initial cycle point)
        Conf('final cycle point', VDR.V_STRING, desc='''
            The (optional) last cycle point at which tasks are run.

            Once all tasks have reached this cycle point, the
            workflow will shut down.

            This item can be overridden on the command line using
            ``cylc play --final-cycle-point`` or ``--fcp``.
        ''')
        Conf('initial cycle point constraints', VDR.V_STRING_LIST, desc='''
            Rules to allow only some initial datetime cycle points.

            .. admonition:: Use Case

               Writing a workflow where users may change the initial
               cycle point, but where only some initial cycle points are
               reasonable.

            Set by defining a list of truncated time points, which
            the initial cycle point must match.

            Examples:

            - ``T00, T06, T12, T18`` - only at 6 hourly intervals.
            -  ``T-30`` - only at half-past an hour.
            - ``01T00`` - only at midnight on the first day of a month.

            .. seealso::

               :ref:`Recurrence tutorial <tutorial-inferred-recurrence>`.

            .. note::

               This setting does not coerce :cylc:conf:`[..]
               initial cycle point = now`.
        ''')
        Conf('final cycle point constraints', VDR.V_STRING_LIST, desc='''
            Rules restricting permitted final cycle points.

            In a cycling workflow it is possible to restrict the final cycle
            point by defining a list of truncated time points under the final
            cycle point constraints.

            .. seealso::

               :ref:`Recurrence tutorial <tutorial-inferred-recurrence>`.

        ''')
        Conf('hold after cycle point', VDR.V_CYCLE_POINT, desc=f'''
            Hold all tasks that pass this cycle point.

            Unlike the final
            cycle point, the workflow does not shut down once all tasks have
            passed this point. If this item is set you can override it on the
            command line using ``--hold-after``.

            .. versionchanged:: 8.0.0

               {REPLACES}``[scheduling]hold after point``.
        ''')
        Conf('stop after cycle point', VDR.V_CYCLE_POINT, desc='''
            Shut down the workflow after all tasks pass this cycle point.

            The stop cycle point can be overridden on the command line using
            ``cylc play --stop-cycle-point=POINT``

            .. note:

               Not to be confused with :cylc:conf:`[..]final cycle point`:
               There can be more graph beyond this point, but you are
               choosing not to run that part of the graph. You can play
               the workflow and continue.

            .. versionadded:: 8.0.0
        ''')
        Conf('cycling mode', VDR.V_STRING, Calendar.MODE_GREGORIAN,
             options=list(Calendar.MODES) + ['integer'], desc='''
            Choice of :term:`integer cycling` or one of several
            :term:`datetime cycling` calendars.

            Cylc runs workflows using the proleptic Gregorian calendar
            by default. This setting allows you to instead choose
            integer cycling, or one of the other supported non-Gregorian
            datetime calendars: 360 day (12 months of 30 days in a year),
            365 day (never a leap year) and 366 day (always a leap year).
        ''')
        Conf('runahead limit', VDR.V_STRING, 'P4', desc='''
            The scheduler runahead limit determines how many consecutive cycle
            points can be active at once. The base point of the runahead
            calculation is the lowest-valued point with :term:`active` or
            :term:`incomplete` tasks present.

            An integer interval value of ``Pn`` allows up to ``n+1`` cycle
            points (including the base point) to be active at once.

            The default runahead limit is ``P4``, i.e. 5 active points
            including the base point.

            Datetime cycling workflows can optionally use a datetime interval
            value instead, in which case the number of active cycle points
            within the interval depends on the cycling intervals present.

            .. seealso::

               :ref:`RunaheadLimit`

            .. versionchanged:: 8.0.0

               The integer format ``Pn`` was introduced to replace the
               deprecated ``[scheduling]max active cycle points = m``
               (with ``n = m-1``) and unify it with the existing datetime
               interval ``runahead limit`` setting.
        ''')

        with Conf('queues', desc='''
            Configuration of internal queues of tasks.

            This section will allow you to limit the number of simultaneously
            active tasks (submitted or running) by assigning tasks to queues.

            By default, a single queue called ``default`` is defined,
            with all tasks assigned to it and no limit to the number of those
            tasks which may be active.

            To use a single queue for the whole workflow, but limit the number
            of active tasks, set :cylc:conf:`[default]limit`.

            To add additional queues define additional sections:

            .. code-block:: cylc

               [[queues]]
                   [[[user_defined_queue]]]
                       limit = 2
                       members = TASK_FAMILY_NAME

            .. seealso::

               :ref:`InternalQueues`.
        '''):
            with Conf('<queue name>', desc='''
                Section heading for configuration of a single queue.
            ''') as Queue:
                Conf('limit', VDR.V_INTEGER, 0, desc='''
                    The maximum number of active tasks allowed at any one
                    time, for this queue.

                    If set to 0 this queue is not limited.
                ''')
                Conf('members', VDR.V_SPACELESS_STRING_LIST, desc='''
                    A list of member tasks, or task family names to assign to
                    this queue.

                    Assigned tasks will automatically be removed
                    from the default queue.
                ''')
            with Conf('default', meta=Queue, desc='''
                The default queue for all tasks not assigned to other queues.
            '''):
                Conf('limit', VDR.V_INTEGER, 100, desc='''
                    Controls the total number of active tasks in the default
                    queue.

                    .. seealso::

                       - :cylc:conf:`flow.cylc[scheduling]
                         [queues][<queue name>]limit`
                       - :ref:`InternalQueues`
                ''')

        with Conf('special tasks', desc='''
            This section is used to identify tasks with special behaviour.

            Family names can be used in special task lists as shorthand for
            listing all member tasks.
        '''):
            Conf('clock-trigger', VDR.V_STRING_LIST, desc='''
            Legacy clock trigger definitions.

            .. deprecated:: 8.0.0

               These are now auto-upgraded to the newer wall_clock xtriggers
               (see :ref:`Section External Triggers`). The old way defining
               clock-triggers will be removed in an upcoming Cylc version.

            Clock-triggered tasks (see :ref:`ClockTriggerTasks`) wait on a wall
            clock time specified as an offset from their own cycle point.

            Example:

            ``foo(PT1H30M), bar(PT1.5H), baz``
            ''')
            Conf('external-trigger', VDR.V_STRING_LIST, desc='''
                Legacy external trigger definition section.

                .. deprecated:: 8.0.0

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
                Don't submit jobs if they are very late in wall clock time.

                Clock-expire tasks enter the ``expired`` state and skip job
                submission if too far behind the wall clock when they become
                ready to run.

                The expiry time is specified as an offset from
                wall-clock time; typically it should be negative - see
                :ref:`ClockExpireTasks`.

                .. note::
                   The offset:

                   * May be positive or negative
                   * The offset may be omitted if it is zero.

                Example:

                ``PT1H`` - 1 hour
            ''')
            Conf('sequential', VDR.V_STRING_LIST, desc='''
                A list of tasks which automatically depend on their own
                previous-cycle instance.

                .. tip::

                   Recommend best practice is now to use explicit inter-cycle
                   triggers rather than sequential tasks.

                .. seealso::

                    :ref:`SequentialTasks`.
            ''')

        with Conf('xtriggers', desc='''
                This section is for *External Trigger* function declarations -
                see :ref:`Section External Triggers`.
        '''):
            Conf('<xtrigger name>', VDR.V_XTRIGGER, desc='''
                Any user-defined event trigger function declarations and
                corresponding labels for use in the graph.

                See :ref:`Section External Triggers` for details.

                Example::

                ``my_trigger(arg1, arg2, kwarg1, kwarg2):PT10S``
            ''')

        with Conf('graph', desc=f'''
            The workflow graph is defined under this section.

            You can plot the dependency graph as you work on it, with
            ``cylc graph``.

            .. seealso::

               :ref:`User Guide Scheduling`.

            .. versionchanged:: 8.0.0

               {REPLACES}``[runtime][dependencies][graph]``.
        '''):
            Conf('<recurrence>', VDR.V_STRING, desc=f'''
                The recurrence defines the sequence of cycle points
                for which the dependency graph is valid.

                .. seealso::

                   :ref:`User Guide Scheduling`

                Cycle points should be specified in our ISO 8601 derived
                sequence syntax, or as integers, in integer cycling mode:

                Example Recurrences:

                datetime cycling:
                   * ``R1`` - once at the initial cycle point
                   * ``T00,T06,T12,T18`` - daily at 00:00, 06:00, 12:00
                     & 18:00
                   * ``PT6H`` - every six hours starting at the initial
                     cycle point
                integer cycling:
                   * ``R1`` - once at the initial cycle point
                   * ``P2`` - every other cycle
                   * ``P3,P5`` - every third or fifth cycle

                .. note::

                   Unlike other Cylc configurations duplicate recurrences
                   are additive and do not override.

                   For example this:

                   .. code-block:: cylc

                      [scheduling]
                          [[graph]]
                              R1 = a => b
                              R1 = c => d

                   Is equivalent to this:

                   .. code-block:: cylc

                      [scheduling]
                          [[graph]]
                              R1 = """
                                  a => b
                                  c => d
                              """

                   See :ref:`GraphTypes` for more on recurrence expressions,
                   and how multiple graphs combine.

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

                .. versionchanged:: 8.0.0

                   {REPLACES}
                   ``[runtime][dependencies][graph][<recurrence>]graph``.
            ''')

    with Conf('runtime',  # noqa: SIM117 (keep same format)
              desc='''
        This section is used to specify settings for tasks to be run.

        You can specify:

        - What scripts or commands you want to execute.
        - Which compute resource (platform) you wish to use.
        - How to run your task.

        If multiple tasks need the same settings, they can share settings by
        inheriting them from one or more other tasks.

        Precedence is determined by the same C3
        linearization algorithm used to find the *method resolution order*
        in Python language class hierarchies.

        .. seealso::

           For details and examples see :ref:`User Guide Runtime`.
    '''):
        with Conf('<namespace>', desc='''
            The name(s) of one or more tasks or task families.

            A namespace (i.e. task or family name) or a comma-separated list
            of namespace names, and repeat as needed to define all tasks in
            the workflow. Names may contain letters, digits, underscores, and
            hyphens.  A namespace represents a group or family of tasks if
            other namespaces inherit from it, or a task if no others inherit
            from it.

            .. important::

               Names may not contain ``:`` or ``.``.

               See :ref:`task namespace rules. <namespace-names>`

            Examples of legal values:

            - ``[foo]``
            - ``[foo, bar, baz]``

            If multiple names are listed the subsequent settings apply to
            all.

            All tasks or task families inherit initially from ``root``, which
            can be explicitly configured to provide or override default
            settings for all tasks in the workflow.
        '''):
            Conf('platform', VDR.V_STRING, desc='''
                The name of a compute resource defined in
                :cylc:conf:`global.cylc[platforms]` or
                :cylc:conf:`global.cylc[platform groups]`.

                The platform specifies the host(s) that the tasks' jobs
                will run on and where (if necessary) files need to be
                installed, and what job runner will be used.

                .. versionadded:: 8.0.0
            ''')
            Conf('inherit', VDR.V_STRING_LIST, desc='''
                A list of the immediate parent(s) of this task or task family.

                If no parents are listed default is ``root``.
            ''')
            Conf('script', VDR.V_STRING, desc=dedent('''
                The main custom script run from the job script.

                It can be an external command or script, or inlined scripting.

                See :ref:`Task Job Script Variables` for the list of variables
                available in the task execution environment.
            ''') + get_script_common_text(
                this='script', example='my_script.sh'
            ))
            Conf('init-script', VDR.V_STRING, desc=dedent('''
                Custom script run by the job script before the task
                execution environment is configured.

                By running before the task execution environment is configured,
                this script does not have
                access to any workflow or task environment variables. It can be
                an external command or script, or inlined scripting. The
                original intention for this item was to allow remote tasks to
                source login scripts to configure their access to cylc, but
                this should no longer be necessary.
            ''') + get_script_common_text(this='init-script'))
            Conf('env-script', VDR.V_STRING, desc=dedent('''
                Custom script run by the job script between the
                cylc-defined environment (workflow and task identity, etc.) and
                the user-defined task runtime environment.

                The env-script has access to the Cylc environment (and the task
                environment has access to variables defined by this scripting).
                It can be an external command or script, or inlined scripting.
            ''') + get_script_common_text(this='env-script'))
            Conf('err-script', VDR.V_STRING, desc=('''
                Script run when a job error is detected.

                Custom script to be run at the end of the error trap,
                which is triggered due to failure of a command in the job
                script or trappable job kill.

                The output of this script will always
                be sent to STDERR and ``$1`` is set to the name of the signal
                caught by the error trap. The script should be fast and use
                very little system resource to ensure that the error trap can
                return quickly.  Companion of :cylc:conf:`[..]exit-script`,
                which is executed on job success.  It can be an external
                command or script, or inlined scripting.
            ''') + get_script_common_text(
                this='err-script', example='echo "Uh oh, received ${1}"'
            ))
            Conf('exit-script', VDR.V_STRING, desc=dedent('''
                Custom script run at the very end of *successful* job
                execution, just before the job script exits.

                The exit-script should execute very quickly.
                Companion of :cylc:conf:`[..]err-script`,
                which is executed on job failure. It can be an external
                command or script, or inlined scripting.
            ''') + get_script_common_text(
                this='exit-script', example='rm -f "$TMP_FILES"'
            ))
            Conf('pre-script', VDR.V_STRING, desc=dedent('''
                Custom script run by the job script immediately
                before :cylc:conf:`[..]script`.

                The pre-script can be an external command or script, or
                inlined scripting.
            ''') + get_script_common_text(
                this='pre-script',
                example='echo "Hello from workflow ${CYLC_WORKFLOW_ID}!"'
            ))
            Conf('post-script', VDR.V_STRING, desc=dedent('''
                Custom script run by the job script immediately
                after :cylc:conf:`[..]script`.

                The post-script can be an external
                command or script, or inlined scripting.
            ''') + get_script_common_text(this='post-script'))

            Conf('work sub-directory', VDR.V_STRING, desc='''
                The directory from which tasks are executed.

                Job scripts are executed from within *work directories*
                created automatically under the workflow run directory. A task
                can get its own work directory from ``$CYLC_TASK_WORK_DIR``
                (or ``$PWD`` if it does not ``cd`` elsewhere at
                runtime). The default directory path contains task name and
                cycle point, to provide a unique workspace for every instance
                of every task. If several tasks need to exchange files and
                simply read and write from their from current working
                directory, setting ``work sub-directory`` can be used to
                override the default to make them all use the same workspace.

                The top level share and work directory location can be changed
                (e.g. to a large data area) by a global config setting (see
                :cylc:conf:`global.cylc[install][symlink dirs]`).

                .. caution::

                   If you omit cycle point from the work sub-directory path
                   successive instances of the task will share the same
                   workspace. Consider the effect on cycle point offset
                   housekeeping of work directories before doing this.

                Example:

                   ``$CYLC_TASK_CYCLE_POINT/shared/``
            ''')
            Conf(
                'execution polling intervals', VDR.V_INTERVAL_LIST, None,
                desc=global_default(
                    EXECUTION_POLL_DESCR,
                    "[platforms][<platform name>]execution polling intervals"
                )
            )
            Conf('execution retry delays', VDR.V_INTERVAL_LIST, None, desc=f'''
                Cylc can automate resubmission of failed jobs.

                Execution retry delays is a list of ISO 8601 durations which
                tell Cylc how long to wait before the next try.

                The job environment variable ``$CYLC_TASK_TRY_NUMBER``
                increments with each automatic retry, allowing you to vary task
                behaviour between retries.

                Tasks only go to the ``failed`` state if job execution fails
                with no retries left.

                .. versionchanged:: 8.0.0

                   {REPLACES}``[runtime][<namespace>][job]execution
                   retry delays``.
            ''')
            Conf('execution time limit', VDR.V_INTERVAL, desc=f'''
                Set the execution (:term:`wallclock <wallclock time>`) time
                limit of a job.

                For ``background`` and ``at`` job runners Cylc runs the
                job's script using the timeout command. For other job runners
                Cylc will convert execution time limit to a :term:`directive`.

                If a job exceeds its execution time limit Cylc can
                poll the job multiple times. You can set polling
                intervals using :cylc:conf:`global.cylc[platforms]
                [<platform name>]execution time limit polling intervals`

                .. versionchanged:: 8.0.0

                   {REPLACES}``[runtime][<namespace>][job]execution
                   time limit``.
            ''')
            Conf(
                'submission polling intervals', VDR.V_INTERVAL_LIST, None,
                desc=global_default(
                    SUBMISSION_POLL_DESCR,
                    "[platforms][<platform name>]submission polling intervals"
                )
            )
            Conf(
                'submission retry delays', VDR.V_INTERVAL_LIST, None,
                desc=global_default(
                    SUBMISSION_RETY_DESCR,
                    "[platforms][<platform name>]submission retry delays"
                )
            )
            Conf(
                'run mode',
                default='live',
                options=['live', 'simulation', 'dummy', 'skip'],
                desc='''
                    Set the run mode for this task. Will override
                    the workflow run mode.

                    TODO: Add docs link
                '''
            )
            with Conf('meta', desc=r'''
                Metadata for the task or task family.

                The ``meta`` section contains metadata items for this task or
                family namespace. The items ``title``, ``description`` and
                ``URL`` are pre-defined and are used by Cylc. Others can be
                user-defined and passed to task event handlers to be
                interpreted according to your needs. For example, the value of
                an "importance" item could determine how an event handler
                responds to task failure events.

                Any workflow meta item can now be passed to task event handlers
                by prefixing the string template item name with ``workflow_``,
                for example:

                .. code-block:: cylc

                   [runtime]
                       [[root]]
                           [[[events]]]
                               failed handlers = """
                                   send-help.sh \
                                       %(workflow_title)s \
                                       %(workflow_importance)s \
                                       %(title)s
                                """
            '''):
                Conf('title', VDR.V_STRING, '', desc='''
                    A single line description of this task or task family.

                    It is displayed by the ``cylc list`` command and can be
                    retrieved from running tasks with the ``cylc show``
                    command.
                ''')
                Conf('description', VDR.V_STRING, '', desc='''
                    A multi-line description of this task or task family.

                    It is retrievable from running tasks with the
                    ``cylc show`` command.
                ''')
                Conf(
                    'URL', VDR.V_STRING, '', desc='''
                        A URL link to task documentation for this task or task
                        family.

                        The templates ``%(workflow)s`` and
                        ``%(task)s`` will be replaced with the actual
                        workflow ID and task name.

                        .. deprecated:: 8.0.0

                           The ``%(suite_name)s`` template variable is
                           deprecated, please use ``%(workflow)s``.

                           The ``%(task_name)s`` template variable is
                           deprecated, please use ``%(task)s``.

                        See also :cylc:conf:`[meta]URL <flow.cylc[meta]URL>`.

                        Example:

                        ``http://my-site.com/workflows/%(workflow)s/'''
                    '%(task)s.html``')
                Conf('<custom metadata>', VDR.V_STRING, '', desc='''
                    Any user-defined metadata item.

                    These, like title, description and URL. can be passed to
                    task event handlers to be interpreted according to your
                    needs. For example, the value of an "importance" item could
                    determine how an event handler responds to task failure
                    events.
                ''')

            with Conf('simulation', desc='''
                Task configuration for workflow *simulation* and *dummy* run
                modes.

                For a full description of simulation and dummy run modes see
                :ref:`SimulationMode`.
            '''):
                Conf('default run length', VDR.V_INTERVAL, DurationFloat(10),
                     desc='''
                    The default simulated job run length.

                    Used if :cylc:conf:`flow.cylc[runtime][<namespace>]
                    execution time limit` **and**
                    :cylc:conf:`flow.cylc[runtime][<namespace>][simulation]
                    speedup factor` are not set.
                ''')
                Conf('speedup factor', VDR.V_FLOAT, desc='''
                    Simulated run length = speedup factor * execution time
                    limit.

                    If :cylc:conf:`flow.cylc[runtime][<namespace>]
                    execution time limit` is set, the task
                    simulated run length is computed by dividing it by this
                    factor.
                ''')
                Conf('time limit buffer', VDR.V_INTERVAL, DurationFloat(30),
                     desc='''
                    For dummy jobs :cylc:conf:`flow.cylc[runtime][<namespace>]
                    execution time limit` is extended
                    by ``time limit buffer``.

                    The time limit buffer is added to prevent dummy jobs
                    being killed after exceeding the ``execution time limit``.
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
                    If ``True`` only the first run of the task
                    instance will fail, otherwise retries will fail too.
                ''')
                Conf('disable task event handlers', VDR.V_BOOLEAN, True,
                     desc='''
                    If ``True`` configured task event handlers
                    will not be called in simulation or dummy modes.
                ''')

            with Conf('skip', desc='''
                Settings for skip mode.

                TODO: Add docs link here.
            '''):
                # Todo We need to expand this somewhere, probably
                # in /cylc/flow/config.py
                # I doubt we can do it until outputs section is parsed.
                Conf(
                    'outputs',
                    VDR.V_STRING_LIST,
                    default=[],
                    desc='''
                        Define the outputs to be generated when this
                        task runs in skip mode. By default, all
                        required outputs will be generated.
                    '''
                )
                Conf(
                    'enable task event handlers',
                    VDR.V_BOOLEAN,
                    default=False,
                    desc='''
                        Enable  the event handlers which would normally
                        be called on task lifecycle events.
                        By default event handers will be turned off
                        in skip mode.
                    '''
                )

            with Conf('environment filter', desc='''
                This section contains environment variable inclusion and
                exclusion lists that can be used to filter the inherited
                environment.

                *This is not intended as an alternative to a
                well-designed inheritance hierarchy that provides each task
                with just the variables it needs.*

                Filters can improve workflows with tasks which inherit a lot
                of environment variables: Filters can make it clear which
                variables each task uses.

                You can use filters as explicit "task environment interfaces".
                They make sure that variables filtered out of the inherited
                environment are not used. However, using filters in this way
                will make your workflow definition longer.

                .. note::
                   Environment filtering is done after inheritance is
                   completely worked out, not at each level on the way, so
                   filter lists in higher-level namespaces only have an effect
                   if they are not overridden by descendants.
            '''):
                Conf('include', VDR.V_STRING_LIST, desc='''
                    If given, **only** variables named in this list will be
                    included from the inherited environment.

                    Other variables will be filtered out. Variables may also
                    be explicitly excluded by an ``exclude`` list.
                ''')
                Conf('exclude', VDR.V_STRING_LIST, desc='''
                    Variables named in this list will be filtered out of the
                    inherited environment.

                    Variables may also be implicitly
                    excluded by omission from an ``include`` list.
                ''')

            with Conf('job', desc=REPLACED_BY_PLATFORMS + dedent('''
                This section configures the means by which cylc submits task
                job scripts to run.
            ''')):
                Conf('batch system', VDR.V_STRING, desc='''
                    .. deprecated:: 8.0.0

                       Kept for back compatibility but replaced by
                       :cylc:conf:`global.cylc[platforms][<platform name>]
                       job runner`.

                    Batch/queuing system (aka job runner) to submit task
                    jobs to.
                ''')
                Conf('batch submit command template', VDR.V_STRING, desc='''
                    .. deprecated:: 8.0.0

                       Kept for back compatibility but replaced by
                       :cylc:conf:`global.cylc[platforms][<platform name>]
                       job runner command template`.

                    Override the default job submission command for the chosen
                    batch system.
                ''')

            with Conf('remote', desc=f'''
                      Job host settings.
                      {REPLACED_BY_PLATFORMS}
             '''):
                Conf('host', VDR.V_STRING, desc=f'''
                     Hostname or IP address of the job host.
                     {REPLACED_BY_PLATFORMS}
                ''')
                Conf('owner', VDR.V_STRING, desc="""
                    Your username on the job host, if different from that on
                    the scheduler host.

                    .. warning::

                       This setting is obsolete at Cylc 8.

                       See :ref:`documentation on changes to remote owner
                       <728.remote_owner>`
                """)
                Conf('retrieve job logs', VDR.V_BOOLEAN,
                     desc=f'''
                     {LOG_RETR_SETTINGS['retrieve job logs']}
                     {REPLACED_BY_PLATFORMS}
                ''')
                Conf('retrieve job logs max size', VDR.V_STRING,
                     desc=f'''
                     {LOG_RETR_SETTINGS['retrieve job logs max size']}
                     {REPLACED_BY_PLATFORMS}
                ''')
                Conf('retrieve job logs retry delays',
                     VDR.V_INTERVAL_LIST, None,
                     desc=f'''
                     {LOG_RETR_SETTINGS['retrieve job logs retry delays']}
                     {REPLACED_BY_PLATFORMS}
                ''')
            with Conf('events', desc=(
                global_default(TASK_EVENTS_DESCR, "[task events]")
            )):
                Conf('execution timeout', VDR.V_INTERVAL, desc=(
                    global_default(
                        TASK_EVENTS_SETTINGS['execution timeout'],
                        "[task events]execution timeout"
                    )
                ))
                Conf('handlers', VDR.V_STRING_LIST, None, desc=(
                    global_default(
                        TASK_EVENTS_SETTINGS['handlers'],
                        "[task events]handlers"
                    )
                ))
                Conf('handler events', VDR.V_STRING_LIST, None, desc=(
                    global_default(
                        TASK_EVENTS_SETTINGS['handler events'],
                        "[task events]handler events"
                    )
                ))
                Conf('handler retry delays', VDR.V_INTERVAL_LIST, None, desc=(
                    global_default(
                        TASK_EVENTS_SETTINGS['handler retry delays'],
                        "[task events]handler retry delays"
                    )
                ))
                Conf('mail events', VDR.V_STRING_LIST, None, desc=(
                    global_default(
                        TASK_EVENTS_SETTINGS['mail events'],
                        "[task events]mail events"
                    )
                ))
                Conf('submission timeout', VDR.V_INTERVAL, desc=(
                    global_default(
                        TASK_EVENTS_SETTINGS['submission timeout'],
                        "[task events]submission timeout"
                    )
                ))
                Conf('expired handlers', VDR.V_STRING_LIST, None, desc='''
                    Handlers to run if this task has expired.

                    .. seealso::

                       :ref:`task-job-states`

                    .. caution::

                       Changes to the scheduling algorithm in Cylc 8 mean
                       this event will not be triggered until the expired task
                       is ready to run.  Earlier expired-task detection will be
                       implemented in a future Cylc release.
                ''')
                Conf('late offset', VDR.V_INTERVAL, None, desc='''
                    Offset from cycle point, in real time, at which this task
                    is considered to be "running late" (i.e. the time by which
                    it would normally have started running).

                    .. caution::

                       Changes to the scheduling algorithm in Cylc 8 mean
                       this event will not be triggered until the late task
                       is ready to run.  Earlier late-task detection will be
                       implemented in a future Cylc release.

                    .. seealso::

                       :cylc:conf:`flow.cylc[runtime][<namespace>][events]
                       late handlers`.
                ''')
                Conf('late handlers', VDR.V_STRING_LIST, None, desc='''
                    Handlers to run if this task is late.

                    .. caution::

                       Due to changes to the Cylc 8 scheduling algorithm
                       this event is unlikely to occur until the task is about
                       to submit anyway.
                ''')
                Conf('submitted handlers', VDR.V_STRING_LIST, None, desc='''
                    Handlers to run when this task is submitted.
                ''')
                Conf('started handlers', VDR.V_STRING_LIST, None, desc='''
                    Handlers to run when this task starts executing.
                ''')
                Conf('succeeded handlers', VDR.V_STRING_LIST, None, desc='''
                    Handlers to run if this task succeeds.
                ''')
                Conf('failed handlers', VDR.V_STRING_LIST, None, desc='''
                    Handlers to run if this task fails.
                ''')
                Conf('submission failed handlers', VDR.V_STRING_LIST, None,
                     desc='''
                        Handlers to run if submission of this task fails.
                ''')
                Conf('warning handlers', VDR.V_STRING_LIST, None, desc='''
                    Handlers to run if this task runs ``cylc message``
                    with severity level "WARNING".
                ''')
                Conf('critical handlers', VDR.V_STRING_LIST, None, desc='''
                    Handlers to run if this task runs ``cylc message``
                    with severity level "CRITICAL".
                ''')
                Conf('retry handlers', VDR.V_STRING_LIST, None, desc='''
                    Handlers to run if this task failed but is retrying.
                ''')
                Conf('submission retry handlers', VDR.V_STRING_LIST, None,
                     desc='''
                        Handlers to run if a job failed to submit but is
                        retrying.

                        .. seealso::

                           :ref:`task-job-states`

                ''')
                Conf('execution timeout handlers', VDR.V_STRING_LIST, None,
                     desc='''
                        Handlers to run if this task execution exceeds
                        :cylc:conf:`flow.cylc[runtime][<namespace>]
                        execution time limit`.
                ''')
                Conf('submission timeout handlers', VDR.V_STRING_LIST, None,
                     desc='''
                        Handlers to run if this task exceeds
                        :cylc:conf:`flow.cylc[runtime][<namespace>][events]
                        submission timeout` in the submitted state.
                ''')
                Conf('custom handlers', VDR.V_STRING_LIST, None, desc='''
                    Handlers to run if this task runs ``cylc message``
                    with severity level "CUSTOM".
                ''')

            with Conf('mail', desc='''
                Email notification settings for task events.

                .. versionadded:: 8.0.0
            '''):
                Conf('from', VDR.V_STRING, desc=f'''
                    Specify an alternate ``from:`` email address for event
                    notifications.

                    .. versionchanged:: 8.0.0

                       {REPLACES}``[runtime][task][events]mail from``
                ''')
                Conf('to', VDR.V_STRING, desc=f'''
                    A list of email addresses to send task event
                    notifications.

                    The list can be any address accepted by the
                    ``mail`` command.

                    .. versionchanged:: 8.0.0

                       {REPLACES}``[runtime][task][events]mail to``
                ''')

            with Conf('workflow state polling', desc=f'''
                Configure automatic workflow polling tasks as described in
                :ref:`WorkflowStatePolling`.

                The items in this section reflect
                options and defaults of the ``cylc workflow-state`` command,
                except that the target workflow ID and the
                ``--task``, ``--cycle``, and ``--status`` options are
                taken from the graph notation.

                .. versionchanged:: 8.0.0

                   {REPLACES}``[runtime][<namespace>]suite state polling``.
            '''):
                Conf('user', VDR.V_STRING, desc='''
                    Username of your account on the workflow host.

                    The polling
                    ``cylc workflow-state`` command will be
                    run on the remote account.
                ''')
                Conf('host', VDR.V_STRING, desc='''
                    The hostname of the target workflow.

                    The polling
                    ``cylc workflow-state`` command will be run there.
                ''')
                Conf('interval', VDR.V_INTERVAL, desc='''
                    Polling interval.
                ''')
                Conf('max-polls', VDR.V_INTEGER, desc='''
                    The maximum number of polls before timing out and entering
                    the "failed" state.
                ''')
                Conf('message', VDR.V_STRING, desc='''
                    Wait for the task in the target workflow to receive a
                    specified message rather than achieve a state.
                ''')
                Conf('run-dir', VDR.V_STRING, desc='''
                    Specify the location of the top level cylc-run directory
                    for the other workflow.

                    For your own workflows, there is no need to set this as it
                    is always ``~/cylc-run/``. But for other workflows,
                    (e.g those owned by others), or mirrored workflow databases
                    use this item to specify the location of the top level
                    cylc run directory (the database should be in a the same
                    place relative to this location for each workflow).
                ''')
                Conf('verbose mode', VDR.V_BOOLEAN, desc='''
                    Run the polling ``cylc workflow-state`` command in verbose
                    output mode.
                ''')

            with Conf('environment', desc='''
                The user defined task execution environment.

                Variables defined here can refer to cylc workflow and task
                identity variables, which are exported earlier in the job
                script. Variable assignment expressions can use cylc
                utility commands because access to cylc is also configured
                earlier in the script.

                .. seealso::

                   :ref:`TaskExecutionEnvironment`.

                You can also specify job environment templates here for
                :ref:`parameterized tasks <User Guide Param>`.
            '''):
                Conf('<variable>', VDR.V_STRING, desc=r'''
                    A custom user defined variable for a task execution
                    environment.

                    The order of definition is preserved that each variable can
                    refer to previously defined
                    variables. Values are passed through to the job
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
                       DICE = [$((($RANDOM % 6) + 1)) $((($RANDOM % 6) + 1))]

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

                    .. note::

                       As with other Cylc configurations, leading or trailing
                       whitespace will be stripped, so the following two
                       examples are equivalent:

                       .. list-table::
                          :class: grid-table

                          * - .. code-block:: cylc

                                 [environment]
                                     FOO = " a "
                                     BAR = """
                                       $(foo bar baz)
                                   """
                            - .. code-block:: cylc

                                 [environment]
                                     FOO = "a"
                                     BAR = "$(foo bar baz)"

                       If leading or trailing whitespace is required, consider
                       using the ``\0`` escape character, or set the variable
                       in :cylc:conf:`[..][..]env-script`.

                    .. versionchanged:: 7.8.7/7.9.2

                       Parameter environment templates (previously in
                       ``[runtime][X][parameter environment templates]``) have
                       moved here.
                ''')

            with Conf('directives', desc=(
                global_default(
                    DIRECTIVES_DESCR,
                    "[platforms][<platform name>][directives]"
                )
            )):
                Conf('<directive>', VDR.V_STRING, desc=DIRECTIVES_ITEM_DESCR)

            with Conf('outputs', desc='''
                Register custom task outputs for use in message triggering in
                this section (:ref:`MessageTriggers`)
            '''):
                Conf('<output>', VDR.V_STRING, desc='''
                    Define custom task outputs (aka :ref:`MessageTriggers`).

                    :term:`Custom outputs <custom output>` allow you to extend
                    the built-in task outputs e.g. ``succeeded`` and ``failed``
                    in order to provide more detailed information about task
                    state. Custom outputs can be used to express dependencies
                    in the graph as with built-in outputs.

                    Custom outputs are defined in the form:

                    .. code-block:: cylc

                       output = message

                    Where ``output`` is the name of the output as it is used in
                    the graph, and ``message`` is the task message sent by
                    the ``cylc message`` command which tells Cylc that this
                    output has been completed. See :ref:`MessageTriggers` for
                    more details.

                    Examples:

                    .. code-block:: cylc

                       out1 = "sea state products ready"
                       out2 = "NWP restart files completed"

                    Custom outputs must satisfy these rules:

                    .. autoclass:: cylc.flow.unicode_rules.TaskOutputValidator

                    Task messages must satisfy these rules:

                    .. autoclass:: cylc.flow.unicode_rules.TaskMessageValidator
                ''')

            with Conf('parameter environment templates', desc='''
                .. deprecated:: 7.8.7/7.9.2

                   Parameter environment templates have moved to
                   :cylc:conf:`flow.cylc[runtime][<namespace>][environment]`.

                This was done to allow users to control the order of
                definition of the variables. This section will be removed
                in a future version of Cylc 8.

                For the time being, the contents of this section will be
                prepended to the ``[environment]`` section when running
                a workflow.
            '''):
                Conf('<parameter>', VDR.V_STRING, desc='''
                    .. deprecated:: 7.8.7/7.9.2

                       Parameter environment templates have moved to
                       :cylc:conf:`flow.cylc[runtime]
                       [<namespace>][environment]`.
                ''')


def upg(cfg, descr):
    """Upgrade old workflow configuration.

    NOTE: We are silencing deprecation (and only deprecation) warnings
    when in Cylc 7 compat mode to help support Cylc 7/8 compatible workflows
    (which would loose Cylc 7 compatibility if users were to follow the
    warnings and upgrade the syntax).

    """
    u = upgrader(cfg, descr)
    u.obsolete(
        '7.8.0',
        ['runtime', '__MANY__', 'suite state polling', 'template'])
    u.obsolete('7.8.1', ['cylc', 'events', 'reset timer'])
    u.obsolete('7.8.1', ['cylc', 'events', 'reset inactivity timer'])
    u.obsolete('8.0.0', ['cylc', 'force run mode'])
    u.obsolete('7.8.1', ['runtime', '__MANY__', 'events', 'reset timer'])
    u.obsolete('8.0.0', ['cylc', 'authentication'], is_section=True)
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
    u.obsolete(
        '8.0.0',
        ['runtime', '__MANY__', 'remote', 'suite definition directory']
    )
    u.obsolete('8.0.0', ['cylc', 'abort if any task fails'])
    u.obsolete('8.0.0', ['cylc', 'disable automatic shutdown'])
    u.obsolete('8.0.0', ['cylc', 'environment'], is_section=True)
    u.obsolete('8.0.0', ['cylc', 'reference test'], is_section=True)
    u.obsolete(
        '8.0.0',
        ['cylc', 'simulation', 'disable suite event handlers'])
    u.obsolete('8.0.0', ['cylc', 'simulation'], is_section=True)
    u.obsolete('8.0.0', ['visualization'], is_section=True)
    u.obsolete('8.0.0', ['scheduling', 'spawn to max active cycle points']),
    u.deprecate(
        '8.0.0',
        ['cylc', 'task event mail interval'],
        ['cylc', 'mail', 'task event batch interval'],
        silent=cylc.flow.flags.cylc7_back_compat,
    )
    u.deprecate(
        '8.0.0',
        ['cylc', 'parameters'],
        ['task parameters'],
        silent=cylc.flow.flags.cylc7_back_compat,
        is_section=True,
    )
    u.deprecate(
        '8.0.0',
        ['cylc', 'parameter templates'],
        ['task parameters', 'templates'],
        silent=cylc.flow.flags.cylc7_back_compat,
        is_section=True,
    )
    # Whole workflow task mail settings
    for mail_setting in ['to', 'from', 'footer']:
        u.deprecate(
            '8.0.0',
            ['cylc', 'events', f'mail {mail_setting}'],
            ['cylc', 'mail', mail_setting],
            silent=cylc.flow.flags.cylc7_back_compat,
        )
    # Task mail settings in [runtime][TASK]
    for mail_setting in ['to', 'from']:
        u.deprecate(
            '8.0.0',
            ['runtime', '__MANY__', 'events', f'mail {mail_setting}'],
            ['runtime', '__MANY__', 'mail', mail_setting],
            silent=cylc.flow.flags.cylc7_back_compat,
        )
    u.deprecate(
        '8.0.0',
        ['cylc', 'events', 'mail smtp'],
        None,  # This is really a .obsolete(), just with a custom message
        cvtr=converter(lambda x: x, (
            'DELETED (OBSOLETE) - use "global.cylc[scheduler][mail]smtp" '
            'instead')
        ),
        silent=cylc.flow.flags.cylc7_back_compat,
    )
    u.deprecate(
        '8.0.0',
        ['runtime', '__MANY__', 'events', 'mail smtp'],
        None,
        cvtr=converter(lambda x: x, (
            'DELETED (OBSOLETE) - use "global.cylc[scheduler][mail]smtp" '
            'instead')
        ),
        silent=cylc.flow.flags.cylc7_back_compat,
    )
    u.deprecate(
        '8.0.0',
        ['scheduling', 'max active cycle points'],
        ['scheduling', 'runahead limit'],
        cvtr=converter(lambda x: f'P{x}' if x != '' else '', '"n" -> "Pn"'),
        silent=cylc.flow.flags.cylc7_back_compat,
    )
    u.deprecate(
        '8.0.0',
        ['scheduling', 'hold after point'],
        ['scheduling', 'hold after cycle point'],
        silent=cylc.flow.flags.cylc7_back_compat,
    )

    u.deprecate(
        '8.0.0',
        ['runtime', '__MANY__', 'suite state polling'],
        ['runtime', '__MANY__', 'workflow state polling'],
        silent=cylc.flow.flags.cylc7_back_compat,
        is_section=True
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
            ['runtime', '__MANY__', job_setting],
            silent=cylc.flow.flags.cylc7_back_compat,
        )

    # Workflow timeout is now measured from start of run.
    # The old timeout was measured from start of stall.
    for old, new in [
        ('timeout', 'stall timeout'),
        ('abort on timeout', 'abort on stall timeout'),
        ('inactivity', 'inactivity timeout'),
        ('abort on inactivity', 'abort on inactivity timeout'),
        ('startup handler', 'startup handlers'),
        ('shutdown handler', 'shutdown handlers'),
        ('timeout handler', 'stall timeout handlers'),
        ('stalled handler', 'stall handlers'),
        ('aborted handler', 'abort handlers'),
        ('inactivity handler', 'inactivity timeout handlers'),
    ]:
        u.deprecate(
            '8.0.0',
            ['cylc', 'events', old],
            ['cylc', 'events', new],
            silent=cylc.flow.flags.cylc7_back_compat,
        )

    for old in [
        "expired handler",
        "late handler",
        "submitted handler",
        "started handler",
        "succeeded handler",
        "failed handler",
        "submission failed handler",
        "warning handler",
        "critical handler",
        "retry handler",
        "submission retry handler",
        "execution timeout handler",
        "submission timeout handler",
        "custom handler"
    ]:
        u.deprecate(
            '8.0.0',
            ['runtime', '__MANY__', 'events', old],
            ['runtime', '__MANY__', 'events', f"{old}s"],
            silent=cylc.flow.flags.cylc7_back_compat,
        )

    u.obsolete('8.0.0', ['cylc', 'events', 'abort on stalled'])
    u.obsolete('8.0.0', ['cylc', 'events', 'abort if startup handler fails'])
    u.obsolete('8.0.0', ['cylc', 'events', 'abort if shutdown handler fails'])
    u.obsolete('8.0.0', ['cylc', 'events', 'abort if timeout handler fails'])
    u.obsolete('8.0.0', ['cylc', 'events',
                         'abort if inactivity handler fails'])
    u.obsolete('8.0.0', ['cylc', 'events', 'abort if stalled handler fails'])

    u.deprecate(
        '8.0.0',
        ['cylc'],
        ['scheduler'],
        silent=cylc.flow.flags.cylc7_back_compat,
        is_section=True,
    )
    u.upgrade()

    upgrade_graph_section(cfg, descr)
    upgrade_param_env_templates(cfg, descr)

    warn_about_depr_platform(cfg)
    warn_about_depr_event_handler_tmpl(cfg)

    return u


def upgrade_graph_section(cfg: Dict[str, Any], descr: str) -> None:
    """Upgrade Cylc 7 `[scheduling][dependencies][X]graph` format to
    `[scheduling][graph]X`."""
    # Parsec upgrader cannot do this type of move
    with contextlib.suppress(KeyError):
        if 'dependencies' in cfg['scheduling']:
            msg_old = '[scheduling][dependencies][X]graph'
            msg_new = '[scheduling][graph]X'
            if 'graph' in cfg['scheduling']:
                raise UpgradeError(
                    f'Cannot upgrade deprecated item "{msg_old} -> {msg_new}" '
                    f'because {msg_new[:-1]} already exists.'
                )
            else:
                keys: Set[str] = set()
                cfg['scheduling'].setdefault('graph', {})
                cfg['scheduling']['graph'].update(
                    cfg['scheduling'].pop('dependencies')
                )
                graphdict: Dict[str, Any] = cfg['scheduling']['graph']
                for key, value in graphdict.copy().items():
                    if isinstance(value, dict) and 'graph' in value:
                        graphdict[key] = value['graph']
                        keys.add(key)
                    elif key == 'graph' and isinstance(value, str):
                        graphdict[key] = value
                        keys.add(key)
                if keys and not cylc.flow.flags.cylc7_back_compat:
                    LOG.warning(
                        'deprecated graph items were automatically upgraded '
                        f'in "{descr}":\n'
                        f' * (8.0.0) {msg_old} -> {msg_new} - for X in:\n'
                        f"       {', '.join(sorted(keys))}"
                    )


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
            if not cylc.flow.flags.cylc7_back_compat:
                if first_warn:
                    LOG.warning(
                        'deprecated items automatically upgraded in '
                        f'"{descr}":'
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
    """Validate platforms config.

    - Warn if deprecated host or batch system appear in config.
    - Raise if platforms section is also present.
    - Or raise if using invalid subshell syntax for platform def.
    """
    if 'runtime' not in cfg:
        return
    for task_name, task_cfg in cfg['runtime'].items():
        if 'platform' in task_cfg and task_cfg['platform']:
            fail_if_platform_and_host_conflict(task_cfg, task_name)
            # Fail if backticks subshell e.g. platform = `foo`:
            is_platform_definition_subshell(task_cfg['platform'])
        elif not cylc.flow.flags.cylc7_back_compat:
            depr = get_platform_deprecated_settings(task_cfg, task_name)
            if depr:
                msg = "\n".join(depr)
                LOG.warning(
                    "deprecated settings found "
                    f"(please replace with [runtime][{task_name}]platform):"
                    f"\n{msg}"
                )


def warn_about_depr_event_handler_tmpl(cfg):
    """Warn if deprecated template strings appear in event handlers."""
    if 'runtime' not in cfg or cylc.flow.flags.cylc7_back_compat:
        return
    deprecation_msg = (
        'The event handler template variable "%({0})s" is deprecated - '
        'use "%({1})s" instead.')
    for task in cfg['runtime']:
        if 'events' not in cfg['runtime'][task]:
            continue
        for handler in cfg['runtime'][task]['events'].values():
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
            if f'%({EventData.Suite.value})' in handler:
                LOG.warning(
                    deprecation_msg.format(EventData.Suite.value,
                                           EventData.Workflow.value)
                )
            if f'%({EventData.SuiteUUID.value})' in handler:
                LOG.warning(
                    deprecation_msg.format(EventData.SuiteUUID.value,
                                           EventData.UUID.value)
                )


class RawWorkflowConfig(ParsecConfig):
    """Raw workflow configuration."""

    def __init__(self, fpath, output_fname, tvars, options):
        """Return the default instance."""
        ParsecConfig.__init__(
            self, SPEC, upg, output_fname, tvars, cylc_config_validate,
            options
        )
        self.loadcfg(fpath, "workflow definition")
