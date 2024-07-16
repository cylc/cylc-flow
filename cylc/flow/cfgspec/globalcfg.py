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
"""Cylc site and user configuration file spec."""

import os
from pathlib import Path
from sys import stderr
from textwrap import dedent
from typing import List, Optional, Tuple, Any, Union

from contextlib import suppress
from packaging.version import Version

from cylc.flow import LOG
from cylc.flow import __version__ as CYLC_VERSION
from cylc.flow.platforms import validate_platforms
from cylc.flow.exceptions import GlobalConfigError
from cylc.flow.hostuserutil import get_user_home
from cylc.flow.network.client_factory import CommsMeth
from cylc.flow.parsec.config import (
    ConfigNode as Conf,
    ParsecConfig,
)
from cylc.flow.parsec.exceptions import (
    ParsecError,
    ItemNotFoundError,
    ValidationError,
)
from cylc.flow.parsec.upgrade import upgrader
from cylc.flow.parsec.util import printcfg, expand_many_section
from cylc.flow.parsec.validate import (
    CylcConfigValidator as VDR,
    DurationFloat,
    Range,
    cylc_config_validate,
)


PLATFORM_REGEX_TEXT = '''
Configured names are regular expressions; any match is a valid platform.
They are searched from the bottom up, until the first match is found.'''


# Nested dict of spec items.
# Spec value is [value_type, default, allowed_2, allowed_3, ...]
# where:
# - value_type: value type (compulsory).
# - default: the default value (optional).
# - allowed_2, ...: the only other allowed values of this setting (optional).

# Standard executable search paths to pass to job submission subprocesses.
SYSPATH = [
    '/bin',
    '/usr/bin',
    '/usr/local/bin',
    '/sbin',
    '/usr/sbin',
    '/usr/local/sbin'
]


REPLACES = 'This item was previously called '
PLATFORM_REPLACES = (
    "(Replaces the deprecated setting "
    ":cylc:conf:`flow.cylc[runtime][<namespace>]{}`.)"
)


PLATFORM_META_DESCR = '''
Metadata for this platform or platform group.

Allows writers of platform configurations to add information
about platform usage. There are no-preset items because
Cylc does not use any platform (or group) metadata internally.

Users can then see information about defined platforms using::

   cylc config -i [platforms]
   cylc config -i [platform groups]

.. seealso::

   :ref:`AdminGuide.PlatformConfigs`

.. versionadded:: 8.0.0
'''

# ----------------------------------------------------------------------------
# Config items shared between global and workflow config:
SCHEDULER_DESCR = f'''
Settings for the scheduler.

.. note::

   Not to be confused with :cylc:conf:`flow.cylc[scheduling]`.

.. versionchanged:: 8.0.0

   {REPLACES}``[cylc]``
'''

UTC_MODE_DESCR = '''
If ``True``, UTC will be used as the time zone for timestamps in
the logs. If ``False``, the local/system time zone will be used.

.. seealso::

   To set a time zone for cycle points, see
   :cylc:conf:`flow.cylc[scheduler]cycle point time zone`.
'''

LOG_RETR_SETTINGS = {
    'retrieve job logs': dedent('''
        Whether to retrieve job logs from the job platform.
    '''),
    'retrieve job logs command': dedent('''
        The command used to retrieve job logs from the job platform.
    '''),
    'retrieve job logs max size': dedent('''
        The maximum size of job logs to retrieve.

        Can be anything
        accepted by the ``--max-size=SIZE`` option of ``rsync``.
    '''),
    'retrieve job logs retry delays': dedent('''
        Configure retries for unsuccessful job log retrieval.

        If there is a significant delay between job completion and
        logs appearing in their final location (due to the job runner)
        you can configure time intervals here to delay the first and
        subsequent retrieval attempts.
    ''')
}

EVENTS_DESCR = '''
Configure the workflow event handling system.
'''

EVENTS_SETTINGS = {  # workflow events
    'handlers': '''
        Configure :term:`event handlers` that run when certain workflow
        events occur.

        This section configures *workflow* event handlers; see
        :cylc:conf:`flow.cylc[runtime][<namespace>][events]` for *task* event
        handlers.

        Event handlers can be held in the workflow ``bin/`` directory,
        otherwise it is up to you to ensure their location is in ``$PATH``
        (in the shell in which the scheduler runs). They should require
        little resource to run and return quickly.

        Template variables can be used to configure handlers. For a full list
        of supported variables see :ref:`workflow_event_template_variables`.

        .. seealso::

           :ref:`user_guide.scheduler.workflow_events`
    ''',
    'handler events': '''
        Specify the events for which workflow event handlers should be invoked.

        .. seealso::

           :ref:`user_guide.scheduler.workflow_events`
    ''',
    'mail events': '''
        Specify the workflow events for which notification emails should
        be sent.
    ''',
    'startup handlers': f'''
        Handlers to run at scheduler startup.

        .. seealso::

           :ref:`user_guide.scheduler.workflow_events`

        .. versionchanged:: 8.0.0

           {REPLACES}``startup handler``.
    ''',
    'shutdown handlers': f'''
        Handlers to run at scheduler shutdown.

        .. seealso::

           :ref:`user_guide.scheduler.workflow_events`

        .. versionchanged:: 8.0.0

           {REPLACES}``shutdown handler``.
    ''',
    'abort handlers': f'''
        Handlers to run if the scheduler shuts down with error status due to
        a configured timeout or a fatal error condition.

        .. seealso::

           :ref:`user_guide.scheduler.workflow_events`

        .. versionchanged:: 8.0.0

           {REPLACES}``aborted handler``.
    ''',
    'workflow timeout': '''
        Workflow timeout interval. The timer starts counting down at scheduler
        startup. It resets on workflow restart.

        .. seealso::

           :ref:`user_guide.scheduler.workflow_events`

        .. versionadded:: 8.0.0
    ''',
    'workflow timeout handlers': '''
        Handlers to run if the workflow timer times out.

        .. seealso::

           :ref:`user_guide.scheduler.workflow_events`

        .. versionadded:: 8.0.0
    ''',
    'abort on workflow timeout': '''
        Whether the scheduler should shut down immediately with error status if
        the workflow timer times out.

        .. seealso::

           :ref:`user_guide.scheduler.workflow_events`

        .. versionadded:: 8.0.0
    ''',
    'stall handlers': f'''
        Handlers to run if the scheduler stalls.

        .. seealso::

           :ref:`user_guide.scheduler.workflow_events`

        .. versionchanged:: 8.0.0

           {REPLACES}``stalled handler``.
    ''',
    'stall timeout': f'''
        The length of a timer which starts if the scheduler stalls.

        .. seealso::

           :ref:`user_guide.scheduler.workflow_events`

        .. versionchanged:: 8.0.0

           {REPLACES}``timeout``.
    ''',
    'stall timeout handlers': f'''
        Handlers to run if the stall timer times out.

        .. seealso::

           :ref:`user_guide.scheduler.workflow_events`

        .. versionchanged:: 8.0.0

           {REPLACES}``timeout handler``.
    ''',
    'abort on stall timeout': f'''
        Whether the scheduler should shut down immediately with error status if
        the stall timer times out.

        .. seealso::

           :ref:`user_guide.scheduler.workflow_events`

        .. versionchanged:: 8.0.0

           {REPLACES}``abort on timeout``.
    ''',
    'inactivity timeout': f'''
        Scheduler inactivity timeout interval. The timer resets when any
        workflow activity occurs.

        .. seealso::

           :ref:`user_guide.scheduler.workflow_events`

        .. versionchanged:: 8.0.0

           {REPLACES} ``inactivity``.
    ''',
    'inactivity timeout handlers': f'''
        Handlers to run if the inactivity timer times out.

        .. seealso::

           :ref:`user_guide.scheduler.workflow_events`

        .. versionchanged:: 8.0.0

           {REPLACES}``inactivity handler``.
    ''',
    'abort on inactivity timeout': f'''
        Whether the scheduler should shut down immediately with error status if
        the inactivity timer times out.

        .. seealso::

           :ref:`user_guide.scheduler.workflow_events`

        .. versionchanged:: 8.0.0

           {REPLACES}``abort on inactivity``.
    ''',
    'restart timeout': '''
        How long to wait for intervention on restarting a completed workflow.
        The timer stops if any task is triggered.

        .. seealso::

           :ref:`user_guide.scheduler.workflow_events`

        .. versionadded:: 8.2.0

    '''
}

MAIL_DESCR = '''
Settings for the scheduler to send event emails.

These settings are used for both workflow and task events.

.. versionadded:: 8.0.0
'''

MAIL_FROM_DESCR = f'''
Specify an alternative ``from`` email address for workflow event notifications.

.. versionchanged:: 8.0.0

   {REPLACES}``[cylc][events]mail from``.
'''

MAIL_TO_DESCR = f'''
A list of email addresses that event notifications should be sent to.

.. versionchanged:: 8.0.0

   {REPLACES}``[cylc][events]mail to``.
'''

MAIL_FOOTER_DESCR = f'''
Specify a string or string template for footers of emails sent for both
workflow and task events.

Template variables may be used in the mail footer. For a list of supported
variables see :ref:`workflow_event_template_variables`.

Example::

   footer = see http://ahost/%(owner)s/notes/%(workflow)s``

.. versionchanged:: 8.0.0

   {REPLACES}``[cylc][events]mail footer``.
'''

MAIL_INTERVAL_DESCR = f'''
Gather all task event notifications in the given interval into a single email.

Useful to prevent being overwhelmed by emails.

.. versionchanged:: 8.0.0

   {REPLACES}``[cylc]task event mail interval``.
'''

MAIN_LOOP_DESCR = '''
Configuration of main loop plugins for the scheduler.

For a list of built in plugins see :ref:`Main Loop Plugins <BuiltInPlugins>`.

.. versionadded:: 8.0.0
'''

MAIN_LOOP_PLUGIN_DESCR = '''
Configure a main loop plugin.

.. note::

   Only the configured list of
   :cylc:conf:`global.cylc[scheduler][main loop]plugins`
   is loaded when a scheduler is started.

.. versionadded:: 8.0.0
'''

MAIN_LOOP_PLUGIN_INTERVAL_DESCR = '''
Interval at which the plugin is invoked.

.. versionadded:: 8.0.0
'''

DIRECTIVES_DESCR = '''
Job runner (batch scheduler) directives.

Supported for use with job runners:

- pbs
- slurm
- loadleveler
- lsf
- sge
- slurm_packjob
- moab

Directives are written to the top of the job script in the correct format
for the job runner.

Specifying directives individually like this allows use of default directives
for task families which can be individually overridden at lower levels of the
runtime namespace hierarchy.
'''

DIRECTIVES_ITEM_DESCR = '''
Example directives for the built-in job runner handlers are shown in
:ref:`AvailableMethods`.
'''

SUBMISSION_POLL_DESCR = f'''
List of intervals at which to poll status of job submission.

Cylc can poll submitted jobs to catch problems that prevent the submitted job
from executing at all, such as deletion from an external job runner queue.

The last value is used repeatedly until the task starts running.

Multipliers can be used as shorthand as in the example below.

Example::

   5*PT2M, PT5M

Note that if the polling
:cylc:conf:`global.cylc[platforms][<platform name>]communication method`
is used then Cylc relies on polling to detect all task state changes,
so you may want to configure more frequent polling.

.. versionchanged:: 8.0.0

   {REPLACES}``[runtime][<namespace>][job]submission polling intervals``.
'''

SUBMISSION_RETY_DESCR = f'''
Cylc can automatically resubmit jobs after submission failures.

Submission retry delays is a list of ISO 8601 durations which tell Cylc
how long to wait before the next try.

The job environment variable ``$CYLC_TASK_SUBMIT_NUMBER`` increments with each
job submission attempt.

Tasks only go to the ``submit-failed`` state if job submission fails with no
retries left.

.. versionchanged:: 8.0.0

   {REPLACES}``[runtime][<namespace>][job]submission retry delays``.
'''

EXECUTION_POLL_DESCR = f'''
List of intervals at which to poll status of job execution.

Cylc can poll running jobs to catch problems that prevent task messages from
being sent back to the workflow, such as hard job kills, network outages, or
unplanned job host shutdown.

The last interval in the list is used repeatedly until the job completes.

Multipliers can be used as shorthand as in the example below.

Example::

   5*PT2M, PT5M

Note that if the polling
:cylc:conf:`global.cylc[platforms][<platform name>]communication method` is
used then Cylc relies on polling to detect all task state changes, so you may
want to configure more frequent polling.

.. versionchanged:: 8.0.0

   {REPLACES}``[runtime][<namespace>][job]execution polling intervals``.
'''

TASK_EVENTS_DESCR = '''
Configure the task event handling system.

See also :cylc:conf:`flow.cylc[scheduler][events]` for *workflow* events.

Task :term:`event handlers` are scripts to run when task events occur.

Event handlers can be stored in the workflow ``bin/`` directory, or
anywhere the scheduler environment ``$PATH``. They should return quickly.

Multiple event handlers can be specified as a list of command line templates.
For supported template variables see :ref:`user_guide.runtime.\
event_handlers.task_event_handling.template_variables`.
Python template substitution syntax is used:
`String Formatting Operations in the Python documentation
<https://docs.python.org/3/library/stdtypes.html
#printf-style-string-formatting>`_.
'''

TASK_EVENTS_SETTINGS = {
    'handlers': '''
        Commands to run on task :cylc:conf:`[..]handler events`.

        A command or list of commands to run for each task event handler
        set in
        :cylc:conf:`flow.cylc[runtime][<namespace>][events]handler events`.

        Information about the event can be provided to the command
        using :ref:`user_guide.runtime.event_handlers.\
task_event_handling.template_variables`.
        For more information, see
        :ref:`user_guide.runtime.task_event_handling`.

        For workflow events, see
        :ref:`user_guide.scheduler.workflow_event_handling`.

        Example::

           echo %(event)s occurred in %(workflow)s >> my-log-file

    ''',
    'execution timeout': '''
        If a task has not finished after the specified interval, the execution
        timeout event handler(s) will be called.
    ''',
    'handler events': '''
        A list of events for which :cylc:conf:`[..]handlers` are run.

        Specify the events for which the general task event handlers
        :cylc:conf:`flow.cylc[runtime][<namespace>][events]handlers`
        should be invoked.

        See :ref:`user_guide.runtime.task_event_handling` for more information.

        Example::

           submission failed, failed
    ''',
    'handler retry delays': '''
        Specify an initial delay before running an event handler command and
        any retry delays in case the command returns a non-zero code.

        The default behaviour is to run an event handler command once without
        any delay.

        Example::

           PT10S, PT1M, PT5M
    ''',
    'mail events': '''
        Specify the events for which notification emails should be sent.

        Example::

           submission failed, failed
    ''',
    'submission timeout': '''
        If a task has not started after the specified interval, the submission
        timeout event handler(s) will be called.
    '''
}

# ----------------------------------------------------------------------------


def short_descr(text: str) -> str:
    """Get dedented one-paragraph description from long description."""
    return dedent(text).split('\n\n', 1)[0]


def default_for(
    text: str, config_path: str, section: bool = False
) -> str:
    """Get dedented short description and insert a 'Default(s) For' directive
    that links to this config item's flow.cylc counterpart."""
    directive = f":Default{'s' if section else ''} For:"
    return (
        f"{directive} :cylc:conf:`flow.cylc{config_path}`.\n\n"
        f"{short_descr(text)}"
    )


with Conf('global.cylc', desc='''
    The global configuration which defines default Cylc Flow settings
    for a user or site.

    To view your global config, run::

       $ cylc config

    Cylc will attempt to load the global configuration (``global.cylc``) from a
    hierarchy of locations, including the site directory (defaults to
    ``/etc/cylc/flow/``) and the user directory (``~/.cylc/flow/``). For
    example at Cylc version 8.0.1, the hierarchy would be, in order of
    ascending priority:

    .. code-block:: sub

       <site-conf-path>/flow/global.cylc
       <site-conf-path>/flow/8/global.cylc
       <site-conf-path>/flow/8.0/global.cylc
       <site-conf-path>/flow/8.0.1/global.cylc
       ~/.cylc/flow/global.cylc
       ~/.cylc/flow/8/global.cylc
       ~/.cylc/flow/8.0/global.cylc
       ~/.cylc/flow/8.0.1/global.cylc

    Where ``<site-conf-path>`` is ``/etc/cylc/flow/`` by default but can be
    changed by :envvar:`CYLC_SITE_CONF_PATH`.

    A setting in a file lower down in the list will override the same setting
    from those higher up (but if a setting is present in a file higher up and
    not in any files lower down, it will not be overridden).

    The following environment variables can change the files which are loaded:

    .. envvar:: CYLC_CONF_PATH

       If set this bypasses the default site/user configuration hierarchy used
       to load the Cylc Flow global configuration.

       This should be set to a directory containing a :cylc:conf:`global.cylc`
       file.

    .. envvar:: CYLC_SITE_CONF_PATH

       By default the site configuration is located in ``/etc/cylc/``. For
       installations where this is not convenient, this path can be overridden
       by setting ``CYLC_SITE_CONF_PATH`` to point at another location.

       Configuration for different Cylc components should be in sub-directories
       within this location.

       For example to configure Cylc Flow you could do the following::

          $CYLC_SITE_CONF_PATH/
          `-- flow/
              `-- global.cylc

    .. note::

       The ``global.cylc`` file can be templated using Jinja2 variables.
       See :ref:`Jinja`.

    .. versionchanged:: 8.0.0

       Prior to Cylc 8, ``global.cylc`` was named ``global.rc``, but that name
       is no longer supported.
''') as SPEC:
    with Conf('hub', desc='''
        Configure the public URL of Jupyter Hub.

        If configured, the ``cylc gui`` command will open a web browser at this
        location rather than starting a standalone server when called.


        .. seealso::

           * The cylc hub :ref:`architecture-reference` for fuller details.
           * :ref:`UI_Server_config` for practical details.

    '''):
        Conf('url', VDR.V_STRING, '', desc='''
            .. versionadded:: 8.3.0

            Where Jupyter Hub is used a url can be provided for routing on
            execution of ``cylc gui`` command.
        ''')

    with Conf('scheduler', desc=(
        default_for(SCHEDULER_DESCR, "[scheduler]", section=True)
    )):
        Conf('UTC mode', VDR.V_BOOLEAN, False, desc=(
            default_for(UTC_MODE_DESCR, "[scheduler]UTC mode")
        ))
        Conf('process pool size', VDR.V_INTEGER, 4, desc='''
            Maximum number of concurrent processes used to execute external job
            submission, event handlers, and job poll and kill commands

            .. seealso::

               :ref:`Managing External Command Execution`.

            .. versionchanged:: 8.0.0

               Moved into the ``[scheduler]`` section from the top level.
        ''')
        Conf('process pool timeout', VDR.V_INTERVAL, DurationFloat(600),
             desc='''
            After this interval Cylc will kill long running commands in the
            process pool.

            .. seealso::

               :ref:`Managing External Command Execution`.

            .. note::

               The default is set quite high to avoid killing important
               processes when the system is under load.

            .. versionchanged:: 8.0.0

               Moved into the ``[scheduler]`` section from the top level.
        ''')
        Conf('auto restart delay', VDR.V_INTERVAL, desc=f'''
            Maximum number of seconds the auto-restart mechanism will delay
            before restarting workflows.

            When a host is set to automatically
            shutdown/restart it waits a random period of time
            between zero and ``auto restart delay`` seconds before
            beginning the process. This is to prevent large numbers of
            workflows from restarting simultaneously.

            .. seealso::

               :ref:`auto-stop-restart`

            .. versionchanged:: 8.0.0

               {REPLACES}``global.rc[suite servers]auto restart delay``.
        ''')
        with Conf('run hosts', desc=f'''
            Configure workflow hosts and ports for starting workflows.

            Additionally configure host selection settings specifying how to
            determine the most suitable run host at any given time from those
            configured.

            .. versionchanged:: 8.0.0

               {REPLACES}``[suite servers]``.
        '''):
            Conf('available', VDR.V_SPACELESS_STRING_LIST, desc=f'''
                A list of workflow run hosts.

                Cylc will choose one of these hosts for a workflow to start on.
                (Unless an explicit host is provided as an option to the
                ``cylc play --host=<myhost>`` command.)

                .. versionchanged:: 8.0.0

                   {REPLACES}``[suite servers]run hosts``.
            ''')
            Conf('ports', VDR.V_RANGE, Range((43001, 43101)),
                 desc=f'''
                The range of ports for Cylc to use to run workflows.

                The minimum and maximum port numbers in the format
                ``min .. max``.

                .. versionchanged:: 8.0.0

                   {REPLACES}``[suite servers]run ports``.
                   It can no longer be used to define a non-contiguous port
                   range.
            ''')
            Conf('condemned', VDR.V_ABSOLUTE_HOST_LIST, desc=f'''
                These hosts will not be used to run jobs.

                If workflows are already running on
                condemned hosts, Cylc will shut them down and
                restart them on different hosts.

                .. seealso::

                   :ref:`auto-stop-restart`

                .. versionchanged:: 8.0.0

                   {REPLACES}``[suite servers]condemned hosts``.
            ''')
            Conf('ranking', VDR.V_STRING, desc=f'''
                Rank and filter run hosts based on system information.

                Ranking can be used to provide load balancing to ensure no
                single run host is overloaded. It also provides thresholds
                beyond which Cylc will not attempt to start new schedulers on
                a host.

                .. _psutil: https://psutil.readthedocs.io/en/latest/

                This should be a multiline string containing Python expressions
                to rank and/or filter hosts. All `psutil`_ attributes are
                available for use in these expressions.

                .. rubric:: Ranking

                Rankings are expressions which return numerical values.
                The host which returns the lowest value is chosen. Examples:

                .. code-block:: python

                   # rank hosts by cpu_percent
                   cpu_percent()

                   # rank hosts by 15min average of server load
                   getloadavg()[2]

                   # rank hosts by the number of cores
                   # (multiple by -1 because the lowest value is chosen)
                   -1 * cpu_count()

                .. rubric:: Threshold

                Thresholds are expressions which return boolean values.
                If a host returns a ``False`` value that host will not be
                selected. Examples:

                .. code-block:: python

                   # filter out hosts with a CPU utilisation of 70% or above
                   cpu_percent() < 70

                   # filter out hosts with less than 1GB of RAM available
                   virtual_memory().available > 1000000000

                   # filter out hosts with less than 1GB of disk space
                   # available on the "/" mount
                   disk_usage('/').free > 1000000000

                .. rubric:: Combining

                Multiple rankings and thresholds can be combined in this
                section e.g:

                .. code-block:: python

                   # filter hosts
                   cpu_percent() < 70
                   disk_usage('/').free > 1000000000

                   # rank hosts by CPU count
                   1 / cpu_count()
                   # if two hosts have the same CPU count
                   # then rank them by CPU usage
                   cpu_percent()

                .. versionchanged:: 8.0.0

                   {REPLACES}``[suite servers][run host select]rank``.
            ''')

        with Conf('host self-identification', desc=f'''
            How Cylc determines and shares the identity of the workflow host.

            The workflow host's identity must be determined locally by cylc and
            passed to running tasks (via ``$CYLC_WORKFLOW_HOST``) so that task
            messages can target the right workflow on the right host.

            .. versionchanged:: 8.0.0

               {REPLACES}``[suite host self-identification]``.
        '''):
            # TODO
            # Is it conceivable that different remote task hosts at the same
            # site might see the workflow host differently? If so we'd need to
            # be able to override the target in workflow configurations.
            Conf(
                'method', VDR.V_STRING, 'name',
                options=['name', 'address', 'hardwired'],
                desc=f'''
                    Determines how cylc finds the identity of the
                    workflow host.

                    Options:

                    name
                       (The default method) Self-identified host name.
                       Cylc asks the workflow host for its host name. This
                       should resolve on task hosts to the IP address of the
                       workflow host; if it doesn't, adjust network settings or
                       use one of the other methods.
                    address
                       Automatically determined IP address (requires *target*).
                       Cylc attempts to use a special external "target address"
                       to determine the IP address of the workflow host as
                       seen by remote task hosts.
                    hardwired
                       (only to be used as a last resort) Manually specified
                       host name or IP address (requires *host*) of the
                       workflow host.

                    .. versionchanged:: 8.0.0

                       {REPLACES}``[suite host self-identification]``.
            ''')
            Conf('target', VDR.V_STRING, 'google.com', desc=f'''
                Target for use by the *address* self-identification method.

                If your workflow host sees the internet, a common
                address such as ``google.com`` will do; otherwise choose a host
                visible on your intranet.

                .. versionchanged:: 8.0.0

                   {REPLACES}``[suite host self-identification]``.
            ''')
            Conf('host', VDR.V_STRING, desc=f'''
                The name or IP address of the workflow host used by the
                *hardwired* self-identification method.

                .. versionchanged:: 8.0.0

                   {REPLACES}``[suite host self-identification]``.
            ''')

        with Conf('events',
                  desc=default_for(EVENTS_DESCR, '[scheduler][events]')):
            for item, desc in EVENTS_SETTINGS.items():
                desc = default_for(desc, f"[scheduler][events]{item}")
                vdr_type = VDR.V_STRING_LIST
                default: Any = Conf.UNSET
                if (
                    item in {'handlers', 'handler events', 'mail events'} or
                    item.endswith("handlers")
                ):
                    pass
                elif item.startswith("abort on"):
                    vdr_type = VDR.V_BOOLEAN
                    default = (item == "abort on stall timeout")
                elif item.endswith("timeout"):
                    vdr_type = VDR.V_INTERVAL
                    if item == "stall timeout":
                        default = DurationFloat(3600)
                    elif item == "restart timeout":
                        default = DurationFloat(120)
                    else:
                        default = None
                Conf(item, vdr_type, default, desc=desc)

        with Conf('mail', desc=(
            default_for(MAIL_DESCR, "[scheduler][mail]", section=True)
        )):
            Conf('from', VDR.V_STRING, desc=(
                default_for(MAIL_FROM_DESCR, "[scheduler][mail]from")
            ))
            Conf('smtp', VDR.V_STRING, desc='''
                Specify the SMTP server for sending workflow event email
                notifications.

                This cannot be configured in ``flow.cylc``.

                Example::

                   smtp.yourorg
            ''')
            Conf('to', VDR.V_STRING, desc=(
                default_for(MAIL_TO_DESCR, "[scheduler][mail]to")
            ))
            Conf('footer', VDR.V_STRING, desc=(
                default_for(MAIL_FOOTER_DESCR, "[scheduler][mail]footer")
            ))
            Conf(
                'task event batch interval',
                VDR.V_INTERVAL,
                DurationFloat(300),
                desc=default_for(
                    MAIL_INTERVAL_DESCR,
                    "[scheduler][mail]task event batch interval"
                )
            )

        with Conf('main loop', desc=(
            default_for(
                MAIN_LOOP_DESCR, "[scheduler][main loop]", section=True
            )
        )):
            Conf(
                'plugins',
                VDR.V_STRING_LIST,
                ['health check', 'reset bad hosts'],
                desc='''
                    Configure the default main loop plugins to use when
                    starting new workflows.

                    Only enabled plugins are loaded. Plugins can be enabled
                    in two ways:

                    Globally:
                       To enable a plugin for all workflows add it to this
                       setting.
                    Per-Run:
                       To enable a plugin for a one-off run of a workflow,
                       specify it on the command line with
                       ``cylc play --main-loop``.

                       .. hint::

                          This *appends* to the configured list of plugins
                          rather than overriding it.

                    .. versionadded:: 8.0.0
            ''')

            with Conf('<plugin name>', desc=(
                default_for(
                    MAIN_LOOP_PLUGIN_DESCR,
                    "[scheduler][main loop][<plugin name>]",
                    section=True
                )
            )) as MainLoopPlugin:
                Conf('interval', VDR.V_INTERVAL, DurationFloat(600), desc=(
                    default_for(
                        MAIN_LOOP_PLUGIN_INTERVAL_DESCR,
                        "[scheduler][main loop][<plugin name>]interval"
                    )
                ))

            with Conf('health check', meta=MainLoopPlugin, desc='''
                Checks the integrity of the workflow run directory.

                .. versionadded:: 8.0.0
            '''):
                Conf('interval', VDR.V_INTERVAL, DurationFloat(600),
                     desc=MAIN_LOOP_PLUGIN_INTERVAL_DESCR)

            with Conf('auto restart', meta=MainLoopPlugin, desc='''
                Automatically migrates workflows between servers.

                For more information see:

                * :ref:`Submitting Workflows To a Pool Of Hosts`.
                * :py:mod:`cylc.flow.main_loop.auto_restart`

                .. versionadded:: 8.0.0
            '''):
                Conf('interval', VDR.V_INTERVAL, DurationFloat(600),
                     desc=MAIN_LOOP_PLUGIN_INTERVAL_DESCR)

            with Conf('reset bad hosts', meta=MainLoopPlugin, desc='''
                Periodically clear the scheduler list of unreachable (bad)
                hosts.

                .. versionadded:: 8.0.0
            '''):
                Conf('interval', VDR.V_INTERVAL, DurationFloat(1800),
                     desc=MAIN_LOOP_PLUGIN_INTERVAL_DESCR)

        with Conf('logging', desc=f'''
            Settings for the workflow event log.

            The workflow event log, held under the workflow run directory, is
            maintained as a rolling archive. Logs are rolled over (backed up
            and started anew) when they reach a configurable limit size.

            .. versionchanged:: 8.0.0

               {REPLACES}``[suite logging]``.
        '''):
            Conf('rolling archive length', VDR.V_INTEGER, 15, desc='''
                How many rolled logs to retain in the archive.
            ''')
            Conf('maximum size in bytes', VDR.V_INTEGER, 1000000, desc='''
                Workflow event logs are rolled over when they reach this
                file size.
            ''')

    with Conf('install', desc='''
        Configure directories and files to be installed on remote hosts.

        .. versionadded:: 8.0.0
    '''):
        Conf('max depth', VDR.V_INTEGER, default=4, desc='''
            How many directory levels deep Cylc should look for installed
            workflows in the :term:`cylc-run directory`.

            This also sets the limit on how deep a :term:`workflow ID` can be
            before ``cylc install`` will refuse to install it. For example,
            if set to 4, ``cylc install one/two/three/four`` will fail,
            because the resultant workflow ID would be
            ``one/two/three/four/run1``, which is 5 levels deep. (However,
            ``cylc install one/two/three/four --no-run-name`` would work.)

            .. note::
               A high value may cause a slowdown of Cylc commands such
               ``install``, ``scan`` and ``clean`` if there are many
               :term:`run directories <run directory>` in the
               cylc-run directory for Cylc to check, or if the filesystem
               is slow (e.g. NFS).

            .. versionadded:: 8.0.0
        ''')
        Conf('source dirs', VDR.V_STRING_LIST, default=['~/cylc-src'], desc='''
            List of paths that Cylc searches for workflows to install.

            All workflow source directories in these locations will
            also show up in the GUI, ready for installation.

            .. note::
               If workflow source directories of the same name exist in more
               than one of these paths, only the first one will be picked up.

            .. versionadded:: 8.0.0
        ''')
        # Symlink Dirs
        with Conf('symlink dirs',  # noqa: SIM117 (keep same format)
                  desc="""
            Configure alternate workflow run directory locations.

            Symlinks from the the standard ``$HOME/cylc-run`` locations will be
            created.

            .. versionadded:: 8.0.0
        """):
            with Conf('<install target>', desc="""
                :ref:`Host <Install targets>` on which to create the symlinks.
            """):
                Conf('run', VDR.V_STRING, None, desc="""
                    Alternative location for the run dir.

                    If specified, the workflow run directory will
                    be created in ``<this-path>/cylc-run/<workflow-id>``
                    and a symbolic link will be created from
                    ``$HOME/cylc-run/<workflow-id>``.
                    If not specified the workflow run directory will be created
                    in ``$HOME/cylc-run/<workflow-id>``.
                    All the workflow files and the ``.service`` directory get
                    installed into this directory.

                    .. versionadded:: 8.0.0
                """)
                Conf('log', VDR.V_STRING, None, desc="""
                    Alternative location for the log dir.

                    If specified the workflow log directory will be created in
                    ``<this-path>/cylc-run/<workflow-id>/log`` and a
                    symbolic link will be created from
                    ``$HOME/cylc-run/<workflow-id>/log``. If not specified
                    the workflow log directory will be created in
                    ``$HOME/cylc-run/<workflow-id>/log``.

                    .. versionadded:: 8.0.0
                """)
                Conf('share', VDR.V_STRING, None, desc="""
                    Alternative location for the share dir.

                    If specified the workflow share directory will be
                    created in ``<this-path>/cylc-run/<workflow-id>/share``
                    and a symbolic link will be created from
                    ``<$HOME/cylc-run/<workflow-id>/share``. If not specified
                    the workflow share directory will be created in
                    ``$HOME/cylc-run/<workflow-id>/share``.

                    .. versionadded:: 8.0.0
                """)
                Conf('share/cycle', VDR.V_STRING, None, desc="""
                    Alternative directory for the share/cycle dir.

                    If specified the workflow share/cycle directory
                    will be created in
                    ``<this-path>/cylc-run/<workflow-id>/share/cycle``
                    and a symbolic link will be created from
                    ``$HOME/cylc-run/<workflow-id>/share/cycle``. If not
                    specified the workflow share/cycle directory will be
                    created in ``$HOME/cylc-run/<workflow-id>/share/cycle``.

                    .. versionadded:: 8.0.0
                """)
                Conf('work', VDR.V_STRING, None, desc="""
                    Alternative directory for the work dir.

                    If specified the workflow work directory will be created in
                    ``<this-path>/cylc-run/<workflow-id>/work`` and a
                    symbolic link will be created from
                    ``$HOME/cylc-run/<workflow-id>/work``. If not specified
                    the workflow work directory will be created in
                    ``$HOME/cylc-run/<workflow-id>/work``.

                    .. versionadded:: 8.0.0
                """)
    with Conf('platforms', desc='''
        Platforms allow you to define compute resources available at your
        site.

        A platform consists of a group of one or more hosts which share a
        file system and a job runner (batch system).

        A platform must allow interaction with the same job from *any*
        of its hosts.

        .. versionadded:: 8.0.0
    '''):
        with Conf('<platform name>', desc='''
            Configuration defining a platform.

            Many of these settings have replaced those of the same name from
            the old Cylc 7 ``suite.rc[runtime][<namespace>][job]/[remote]``
            and ``global.rc[hosts][<host>]`` sections.

            Platform names can be regular expressions: If you have a set of
            compute resources such as ``bigmachine1, bigmachine2`` or
            ``desktop0000, .., desktop9999`` one would define platforms with
            names ``[[bigmachine[12]]]`` and ``[[desktop[0-9]{4}]]``.

            Cylc searches for a matching platform in the reverse
            of the definition order to allow user defined platforms
            to override site defined platforms. This means, for example, that
            if ``[[a.*]]`` were set at the bottom of a configuration any
            platform name beginning with "a" would return that platform.

            .. note::

               Each possible match to the definition regular expression is
               considered a separate platform.

               If you had a supercomputer with multiple login nodes this would
               be a single platform with multiple :cylc:conf:`hosts`.

            .. warning::

               ``[platforms][localhost]`` may be set, to override default
               settings, but regular expressions which match "localhost"
               may not. Use comma separated lists instead:

               .. code-block:: cylc

                  [platforms]
                      [[localhost|cylc-server-..]]  # error
                      [[localhost, cylc-server-..]]  # ok

            .. seealso::

               - :ref:`MajorChangesPlatforms` in the Cylc 8 migration guide.
               - :ref:`AdminGuide.PlatformConfigs`, an administrator's guide to
                 platform configurations.

            .. versionadded:: 8.0.0
        ''') as Platform:
            with Conf('meta', desc=PLATFORM_META_DESCR):
                Conf('<custom metadata>', VDR.V_STRING, '', desc='''
                    Any user-defined metadata item.

                    .. versionadded:: 8.0.0
                ''')
            Conf('hosts', VDR.V_STRING_LIST, desc='''
                A list of hosts from which the job host can be selected using
                :cylc:conf:`[..][selection]method`.

                All hosts should share a file system.

                .. versionadded:: 8.0.0
            ''')
            Conf('job runner', VDR.V_STRING, 'background', desc=f'''
                The system used to run jobs on the platform.

                Examples:

                 * ``background``
                 * ``slurm``
                 *  ``pbs``

                .. seealso::

                   :ref:`List of built-in Job Runners <AvailableMethods>`

                .. versionadded:: 8.0.0

                   {PLATFORM_REPLACES.format("[job]batch system")}
            ''')
            replaces = PLATFORM_REPLACES.format(
                "[job]batch submit command template"
            )
            Conf('job runner command template', VDR.V_STRING, desc=f'''
                Set the command used by the chosen job runner.

                The template's ``%(job)s`` will be
                substituted by the job file path.

                .. versionadded:: 8.0.0

                   {replaces}
            ''')
            Conf('shell', VDR.V_STRING, '/bin/bash', desc='''

                .. versionchanged:: 8.0.0

                   Moved from ``suite.rc[runtime][<namespace>]job``.
            ''')
            Conf('communication method',
                 VDR.V_STRING, 'zmq',
                 options=[meth.value for meth in CommsMeth], desc=f'''
                The means by which task progress messages are reported back to
                the running workflow.

                ..rubric:: Options:

                zmq
                   Direct client-server TCP communication via network ports
                poll
                   The workflow polls for task status (no task messaging)
                ssh
                   Use non-interactive ssh for task communications

                For more information, see :ref:`TaskComms`.

                .. versionchanged:: 8.0.0

                   {REPLACES}``global.rc[hosts][<host>]task communication
                   method``.
            ''')
            Conf(
                'submission polling intervals', VDR.V_INTERVAL_LIST,
                [DurationFloat(900)], desc=default_for(
                    SUBMISSION_POLL_DESCR,
                    "[runtime][<namespace>]submission polling intervals"
                )
            )
            Conf(
                'submission retry delays', VDR.V_INTERVAL_LIST, None,
                desc=default_for(
                    SUBMISSION_RETY_DESCR,
                    "[runtime][<namespace>]submission retry delays"
                )
            )
            Conf(
                'execution polling intervals', VDR.V_INTERVAL_LIST,
                [DurationFloat(900)], desc=default_for(
                    EXECUTION_POLL_DESCR,
                    "[runtime][<namespace>]execution polling intervals"
                )
            )
            Conf('execution time limit polling intervals',
                 VDR.V_INTERVAL_LIST,
                 [DurationFloat(60), DurationFloat(120), DurationFloat(420)],
                 desc=f'''
                List of intervals after execution time limit to poll jobs.

                If a job exceeds its execution time limit, Cylc can poll
                more frequently to detect the expected job completion quickly.
                The last interval in the list is used repeatedly until the job
                completes.
                Multipliers can be used as shorthand as in the example below.

                Example::

                   5*PT2M, PT5M

                .. versionchanged:: 8.0.0

                   {REPLACES}``global.rc[hosts][<host>][batch systems]
                   [<system>]execution time limit polling``.
            ''')
            Conf('ssh command',
                 VDR.V_STRING,
                 'ssh -oBatchMode=yes -oConnectTimeout=10',
                 desc=f'''
                A communication command used to invoke commands on this
                platform.

                Not used on the workflow host unless you run local tasks
                under another user account.  The value is assumed to be ``ssh``
                with some initial options or a command that implements a
                similar interface to ``ssh``.

                .. versionchanged:: 8.0.0

                   {REPLACES}``global.rc[hosts][<host>]ssh command``.
            ''')
            Conf('rsync command',
                 VDR.V_STRING,
                 'rsync',
                 desc='''
                Command used for file installation.

                This supports POSIX compliant rsync implementations e.g. GNU or
                BSD.

                .. versionadded:: 8.0.0
            ''')
            Conf('use login shell', VDR.V_BOOLEAN, True, desc=f'''
                Whether to use a login shell or not for remote command
                invocation.

                By default, Cylc runs remote SSH commands using a login shell:

                .. code-block:: bash

                   ssh user@host 'bash --login cylc ...'

                which will source the following files (in order):

                * ``/etc/profile``
                * ``~/.bash_profile``
                * ``~/.bash_login``
                * ``~/.profile``

                .. _Bash man pages: https://linux.die.net/man/1/bash

                For more information on login shells see the "Invocation"
                section of the `Bash man pages`_.

                For security reasons some institutions do not allow unattended
                commands to start login shells, so you can turn off this
                behaviour to get:

                .. code-block:: bash

                   ssh user@host 'cylc ...'

                which will use the default shell on the remote machine,
                sourcing ``~/.bashrc`` (or ``~/.cshrc``) to set up the
                environment.

                .. versionchanged:: 8.0.0

                   {REPLACES}``global.rc[hosts][<host>]use login shell``.
            ''')
            Conf('cylc path', VDR.V_STRING, desc='''
                The path containing the ``cylc`` executable on a remote
                platform.

                This may be necessary if the ``cylc`` executable is not in the
                ``$PATH`` for an ``ssh`` call.
                Test whether this is the case by using
                ``ssh <host> command -v cylc``.

                This path is used for remote invocations of the ``cylc``
                command and is added to the ``$PATH`` in job scripts
                for the configured platform.

                .. note::

                   If :cylc:conf:`[..]use login shell = True` (the default)
                   then an alternative approach is to add ``cylc`` to the
                   ``$PATH`` in the system or user Bash profile files
                   (e.g. ``~/.bash_profile``).

                .. tip::

                   For multi-version installations this should point to the
                   Cylc wrapper script rather than the ``cylc`` executable
                   itself.

                   See :ref:`managing environments` for more information on
                   the wrapper script.

                .. versionchanged:: 8.0.0

                   Moved from ``suite.rc[runtime][<namespace>][job]
                   cylc executable``.
            ''')
            Conf('global init-script', VDR.V_STRING, desc=f'''
                A per-platform script which is run before other job scripts.

                This should be used sparingly to perform any shell
                configuration that cannot be performed via other means.

                .. versionchanged:: 8.0.0

                   The ``global init-script`` now runs *before* any job
                   scripting which introduces caveats outlined below.

                .. warning::

                   The ``global init-script`` has the following caveats,
                   as compared to the other task ``script-*`` items:

                   * The script is not covered by error trapping.
                   * The job environment is not available to this script.
                   * In debug mode this script will not be included in
                     xtrace output.

                .. versionchanged:: 8.0.0

                   {REPLACES}``global.rc[hosts][<host>]global init-script``.
            ''')
            Conf('copyable environment variables', VDR.V_STRING_LIST, '',
                 desc=f'''
                A list containing the names of the environment variables to
                be copied from the scheduler to a job.

                .. versionchanged:: 8.0.0

                   {REPLACES}``global.rc[hosts][<host>]copyable
                   environment variables``.
            ''')
            Conf('retrieve job logs', VDR.V_BOOLEAN,
                 desc=f'''
                {LOG_RETR_SETTINGS['retrieve job logs']}

                .. versionchanged:: 8.0.0

                   {REPLACES}``global.rc[hosts][<host>]retrieve job logs``.
                   {PLATFORM_REPLACES.format("[remote]retrieve job logs")}
            ''')
            Conf('retrieve job logs command', VDR.V_STRING, 'rsync -a',
                 desc=f'''
                {LOG_RETR_SETTINGS['retrieve job logs command']}

                .. note::
                   The default command (``rsync -a``) means that the retrieved
                   files (and the directories above including ``job/log``) get
                   the same permissions as on the remote host. This can cause
                   problems if the remote host uses different permissions to
                   the scheduler host (e.g. no world read access). To avoid
                   this problem you can set the command to
                   ``rsync -a --no-p --no-g --chmod=ugo=rwX`` which means the
                   retrieved files get the default permissions used on the
                   scheduler host.

                .. versionchanged:: 8.0.0

                   {REPLACES}``global.rc[hosts][<host>]retrieve job logs
                   command``.
            ''')
            replaces = PLATFORM_REPLACES.format(
                "[remote]retrieve job logs max size")
            Conf('retrieve job logs max size', VDR.V_STRING, desc=f'''
                {LOG_RETR_SETTINGS['retrieve job logs max size']}

                .. versionchanged:: 8.0.0

                   {REPLACES}``global.rc[hosts][<host>]retrieve job logs
                   max size``.
                   {replaces}
            ''')
            replaces = PLATFORM_REPLACES.format(
                "[remote]retrieve job logs retry delays")
            Conf('retrieve job logs retry delays', VDR.V_INTERVAL_LIST,
                 desc=f'''
                {LOG_RETR_SETTINGS['retrieve job logs retry delays']}

                .. versionchanged:: 8.0.0

                   {REPLACES}``global.rc[hosts][<host>]retrieve job logs
                   retry delays``.
                   {replaces}
            ''')
            Conf('tail command template',
                 VDR.V_STRING, 'tail -n +1 --follow=name %(filename)s',
                 desc=f'''
                A command template (with ``%(filename)s`` substitution) to
                tail-follow job logs this platform, by ``cylc cat-log``.

                .. warning::

                   You are are unlikely to need to override this. Doing so may
                   adversely affect the UI log view.

                .. versionchanged:: 8.0.0

                   {REPLACES}``global.rc[hosts][<host>]tail command template``.
            ''')
            Conf('err tailer', VDR.V_STRING, desc=f'''
                A command template (with ``%(job_id)s`` substitution) that can
                be used to tail-follow the stderr stream of a running job if
                SYSTEM does not use the normal log file location while the job
                is running.  This setting overrides
                :cylc:conf:`[..]tail command template`.

                Examples::

                   # for PBS
                   qcat -f -e %(job_id)s

                .. versionchanged:: 8.0.0

                   {REPLACES}``global.rc[hosts][<host>][batch systems]
                   [<system>]err tailer``.
            ''')
            Conf('out tailer', VDR.V_STRING, desc=f'''
                A command template (with ``%(job_id)s`` substitution) that can
                be used to tail-follow the stdout stream of a running job if
                SYSTEM does not use the normal log file location while the job
                is running.  This setting overrides
                :cylc:conf:`[..]tail command template`.

                Examples::

                   # for PBS
                   qcat -f -o %(job_id)s

                .. versionchanged:: 8.0.0

                   {REPLACES}``global.rc[hosts][<host>][batch systems]
                   [<system>]out tailer``.
            ''')
            Conf('err viewer', VDR.V_STRING, desc=f'''
                A command template (with ``%(job_id)s`` substitution) that can
                be used to view the stderr stream of a running job if SYSTEM
                does not use the normal log file location while the job is
                running.

                Examples::

                   # for PBS
                   qcat -e %(job_id)s

                .. versionchanged:: 8.0.0

                   {REPLACES}``global.rc[hosts][<host>][batch systems]
                   [<system>]err viewer``.
            ''')
            Conf('out viewer', VDR.V_STRING, desc=f'''
                A command template (with ``%(job_id)s`` substitution) that can
                be used to view the stdout stream of a running job if SYSTEM
                does not use the normal log file location while the job is
                running.

                Examples::

                   # for PBS
                   qcat -o %(job_id)s

                .. versionchanged:: 8.0.0

                   {REPLACES}``global.rc[hosts][<host>][batch systems]
                   [<system>]out viewer``.
            ''')
            Conf('job name length maximum', VDR.V_INTEGER, desc=f'''
                The maximum length for job name acceptable by a job runner on
                a given host.  Currently, this setting is only meaningful for
                PBS jobs. For example, PBS 12 or older will fail a job submit
                if the job name has more than 15 characters; whereas PBS 13
                accepts up to 236 characters.

                .. versionchanged:: 8.0.0

                   {REPLACES}``global.rc[hosts][<host>][batch systems]
                   [<system>]job name length maximum``.
            ''')
            Conf('install target', VDR.V_STRING, desc='''
                This defaults to the platform name. This will be used as the
                target for remote file installation.
                For example, if Platform_A shares a file system with localhost:

                .. code-block:: cylc

                   [platforms]
                       [[Platform_A]]
                           install target = localhost

                .. versionadded:: 8.0.0
            ''')

            Conf('clean job submission environment', VDR.V_BOOLEAN, False,
                 desc='''
                Job submission subprocesses inherit their parent environment by
                default. Remote jobs inherit the default non-interactive shell
                environment for their platform. Jobs on the scheduler host
                inherit the scheduler environment (unless their job runner
                prevents this).

                If, for example, the ``$PYTHON`` variable is different on the
                scheduler and the remote host the same program  may run in
                different ways.

                We recommend using a clean job submission environment for
                consistent handling of local and remote jobs. However,
                this is not the default behaviour because it prevents
                local jobs from running, unless ``$PATH`` contains the
                ``cylc`` wrapper script.

                Specific environment variables can be singled out to pass
                through to the clean environment, if necessary.

                A standard set of executable paths is passed through to clean
                environments, and can be added to if necessary.

                .. versionadded:: 8.0.0
            ''')

            Conf('job submission environment pass-through', VDR.V_STRING_LIST,
                 desc='''
                List of environment variable names to pass through to
                job submission subprocesses.

                ``$HOME`` is passed automatically.

                You are unlikely to need this.

                .. versionadded:: 8.0.0
            ''')
            Conf('job submission executable paths', VDR.V_STRING_LIST,
                 desc=f'''
                Additional executable locations to pass to the job
                submission subprocess beyond the standard locations
                {", ".join(f"``{i}``" for i in SYSPATH)}.
                You are unlikely to need this.

                .. versionadded:: 8.0.0
            ''')
            Conf('max batch submit size', VDR.V_INTEGER, default=100, desc='''
                Limits the maximum number of jobs that can be submitted at
                once.

                Where possible Cylc will batch together job submissions to
                the same platform for efficiency. Submitting very large
                numbers of jobs can cause problems with some submission
                systems so for safety there is an upper limit on the number
                of job submissions which can be batched together.

                .. versionadded:: 8.0.0
            ''')
            Conf('ssh forward environment variables', VDR.V_STRING_LIST, '',
                 desc='''
                A list containing the names of the environment variables to
                forward with SSH connections to the workflow host from
                the host running 'cylc play'

                .. versionadded:: 8.3.0
            ''')
            with Conf('selection', desc='''
                How to select a host from the list of platform hosts.

                .. versionadded:: 8.0.0
            ''') as Selection:
                Conf('method', VDR.V_STRING, default='random',
                     options=['random', 'definition order'],
                     desc='''
                    Host selection method for the platform.

                    .. rubric:: Available options

                    - ``random``: Choose randomly from the list of hosts.
                      This is suitable for a pool of identical hosts.
                    - ``definition order``: Take the first host in the list
                      unless that host was unreachable. In many cases
                      this is likely to cause load imbalances, but might
                      be appropriate if following the pattern
                      ``hosts = main, backup, failsafe``.

                    .. versionadded:: 8.0.0
                ''')
            with Conf('directives', desc=(
                default_for(
                    DIRECTIVES_DESCR,
                    "[runtime][<namespace>][directives]",
                    section=True
                ) + "\n\n" + ".. versionadded:: 8.0.0"
            )):
                Conf('<directive>', VDR.V_STRING,
                     desc=short_descr(DIRECTIVES_ITEM_DESCR))

        with Conf('localhost', meta=Platform, desc='''
            A default platform for running jobs on the the scheduler host.

            This platform configures the host on which
            :term:`schedulers <scheduler>` run. By default this is the
            host where ``cylc play`` is run, however, we often configure
            Cylc to start schedulers on dedicated hosts by configuring
            :cylc:conf:`global.cylc[scheduler][run hosts]available`.

            This platform affects connections made to the scheduler host and
            any jobs run on it.

            .. versionadded:: 8.0.0
        '''):
            Conf('hosts', VDR.V_STRING_LIST, ['localhost'], desc='''
                List of hosts for the localhost platform. You are unlikely to
                need to change this.

                The scheduler hosts are configured by
                :cylc:conf:`global.cylc[scheduler][run hosts]available`.
                See :ref:`Submitting Workflows To a Pool Of Hosts` for
                more information.

                .. seealso::

                   :cylc:conf:`global.cylc[platforms][<platform name>]hosts`
            ''')
            with Conf(
                'selection', meta=Selection,
                desc=(
                    'How to select a host on the "localhost" platform.'
                    'You are unlikely to need to change this.'
                    ':cylc:conf:`global.cylc[platforms][<platform name>]'
                    '[selection]`'
                )
            ):
                Conf('method', VDR.V_STRING, default='definition order',
                     desc='''
                        Host selection method for the "localhost" platform.

                        .. seealso::

                           :cylc:conf:`global.cylc[platforms][<platform name>]
                           [selection]method`
                ''')

    # Platform Groups
    with Conf('platform groups', desc='''
        Platform groups allow you to group together platforms which would
        all be suitable for a given job.


        When Cylc submits a job it will pick a platform from a group.
        Cylc will then use the selected platform for all interactions with
        that job.

        For example, if you have a group of computers
        without a shared file system, but otherwise identical called
        ``bigmachine01..02`` you might set up a platform group
        ``[[bigmachines]]platforms=bigmachine01, bigmachine02``.

        .. seealso::

           - :ref:`MajorChangesPlatforms` in the Cylc 8 migration guide.
           - :ref:`AdminGuide.PlatformConfigs`, an guide to platform
             configurations.

        .. versionadded:: 8.0.0
    '''):  # noqa: SIM117 (keep same format)
        with Conf('<group>', desc='''
        The name of a :cylc:conf:`platform group
        <global.cylc[platform groups]>`.
        '''):
            with Conf('meta', desc=PLATFORM_META_DESCR):
                Conf('<custom metadata>', VDR.V_STRING, '', desc='''
                    Any user-defined metadata item.

                    .. versionadded:: 8.0.0
                ''')
            Conf('platforms', VDR.V_STRING_LIST, desc='''
                A list of platforms which can be selected if
                :cylc:conf:`flow.cylc[runtime][<namespace>]platform` matches
                the name of this platform group.

                .. versionadded:: 8.0.0

                .. note::

                   Some job runners ("background", "at") require a single-host
                   platform, because the job ID is only valid on the submission
                   host.

            ''')
            with Conf(
                'selection',
                desc='Sets how platforms are selected from platform groups.'
            ):
                Conf(
                    'method', VDR.V_STRING, default='random',
                    options=['random', 'definition order'],
                    desc='''
                        Method for selecting platform from group.

                        options:

                        - random: Suitable for an identical pool of platforms.
                        - definition order: Pick the first available platform
                          from the list.

                        .. versionadded:: 8.0.0
                    '''
                )
    # task
    with Conf('task events', desc=(
        default_for(
            TASK_EVENTS_DESCR, "[runtime][<namespace>][events]", section=True
        ) + "\n\n" + ".. versionadded:: 8.0.0"
    )):
        Conf('execution timeout', VDR.V_INTERVAL, desc=(
            default_for(
                TASK_EVENTS_SETTINGS['execution timeout'],
                "[runtime][<namespace>][events]execution timeout"
            )
        ))
        Conf('handlers', VDR.V_STRING_LIST, desc=(
            default_for(
                TASK_EVENTS_SETTINGS['handlers'],
                "[runtime][<namespace>][events]handlers"
            )
        ))
        Conf('handler events', VDR.V_STRING_LIST, desc=(
            default_for(
                TASK_EVENTS_SETTINGS['handler events'],
                "[runtime][<namespace>][events]handler events"
            )
        ))
        Conf('handler retry delays', VDR.V_INTERVAL_LIST, None, desc=(
            default_for(
                TASK_EVENTS_SETTINGS['handler retry delays'],
                "[runtime][<namespace>][events]handler retry delays"
            )
        ))
        Conf('mail events', VDR.V_STRING_LIST, desc=(
            default_for(
                TASK_EVENTS_SETTINGS['mail events'],
                "[runtime][<namespace>][events]mail events"
            )
        ))
        Conf('submission timeout', VDR.V_INTERVAL, desc=(
            default_for(
                TASK_EVENTS_SETTINGS['submission timeout'],
                "[runtime][<namespace>][events]submission timeout"
            )
        ))


def upg(cfg, descr):
    """Upgrader."""
    u = upgrader(cfg, descr)
    u.upgrade()


def get_version_hierarchy(version: str) -> List[str]:
    """Return list of versions whose global configs are compatible, in
    ascending priority.

    Args:
        version: A PEP 440 compliant version tag.

    Example:
        >>> get_version_hierarchy('8.0.1a2.dev')
        ['', '8', '8.0', '8.0.1', '8.0.1a2', '8.0.1a2.dev']

    """
    smart_ver = Version(version)
    base = [str(i) for i in smart_ver.release]
    hierarchy = ['']
    hierarchy += ['.'.join(base[:i]) for i in range(1, len(base) + 1)]
    if smart_ver.pre:  # alpha/beta (excluding dev) part of version
        pre_ver = ''.join(str(i) for i in smart_ver.pre)
        hierarchy.append(f'{hierarchy[-1]}{pre_ver}')
    if version not in hierarchy:  # catch-all
        hierarchy.append(version)
    return hierarchy


class GlobalConfig(ParsecConfig):
    """
    Handle global (all workflows) site and user configuration for cylc.
    User file values override site file values.
    """

    _DEFAULT: Optional['GlobalConfig'] = None
    CONF_BASENAME: str = "global.cylc"
    DEFAULT_SITE_CONF_PATH: str = os.path.join(os.sep, 'etc', 'cylc')
    USER_CONF_PATH: str = os.path.join(
        os.getenv('HOME') or get_user_home(), '.cylc', 'flow'
    )
    VERSION_HIERARCHY: List[str] = get_version_hierarchy(CYLC_VERSION)

    def __init__(self, *args, **kwargs) -> None:
        site_conf_root = (
            os.getenv('CYLC_SITE_CONF_PATH') or self.DEFAULT_SITE_CONF_PATH
        )
        self.conf_dir_hierarchy: List[Tuple[str, str]] = [
            *[
                (upgrader.SITE_CONFIG,
                 os.path.join(site_conf_root, 'flow', ver))
                for ver in self.VERSION_HIERARCHY
            ],
            *[
                (upgrader.USER_CONFIG,
                 os.path.join(self.USER_CONF_PATH, ver))
                for ver in self.VERSION_HIERARCHY
            ]
        ]
        super().__init__(*args, **kwargs)

    @classmethod
    def get_inst(cls, cached: bool = True) -> 'GlobalConfig':
        """Return a GlobalConfig instance.

        Args:
            cached (bool):
                If cached create if necessary and return the singleton
                instance, else return a new instance.
        """
        if not cached:
            # Return an up-to-date global config without affecting the
            # singleton.
            new_instance = cls(SPEC, upg, validator=cylc_config_validate)
            new_instance.load()
            return new_instance
        elif not cls._DEFAULT:
            cls._DEFAULT = cls(SPEC, upg, validator=cylc_config_validate)
            cls._DEFAULT.load()
        return cls._DEFAULT

    def _load(self, fname: Union[Path, str], conf_type: str) -> None:
        if not os.access(fname, os.F_OK | os.R_OK):
            return
        try:
            self.loadcfg(fname, conf_type)
            self._validate_source_dirs()
        except ParsecError:
            LOG.error(f'bad {conf_type} {fname}')
            raise

    def load(self) -> None:
        """Load or reload configuration from files."""
        self.sparse.clear()
        self.dense.clear()
        LOG.debug("Loading site/user config files")
        conf_path_str = os.getenv("CYLC_CONF_PATH")
        if conf_path_str:
            # Explicit config file override.
            fname = os.path.join(conf_path_str, self.CONF_BASENAME)
            self._load(fname, upgrader.USER_CONFIG)
        else:
            # Use default locations.
            for conf_type, conf_dir in self.conf_dir_hierarchy:
                fname = os.path.join(conf_dir, self.CONF_BASENAME)
                self._load(fname, conf_type)

        # Expand platforms needs to be performed first because it
        # manipulates the sparse config.
        self._expand_platforms()

        # Flesh out with defaults
        self.expand()

        self._no_platform_group_name_overlap()
        with suppress(KeyError):
            validate_platforms(self.sparse['platforms'])

    def _validate_source_dirs(self) -> None:
        """Check source dirs are absolute paths."""
        keys = ['install', 'source dirs']
        try:
            src_dirs: List[str] = self.get(keys, sparse=True)
        except ItemNotFoundError:
            return
        for item in src_dirs:
            path = Path(item)
            # Do not expand user/env vars - it is ok if they don't exist
            if not (
                path.is_absolute() or path.parts[0].startswith(('~', '$'))
            ):
                raise ValidationError(
                    keys, value=item, msg="must be an absolute path"
                )

    def _no_platform_group_name_overlap(self):
        if (
            'platforms' in self.sparse and
            'platform groups' in self.sparse
        ):
            names_in_platforms_and_groups = set(
                self.sparse['platforms'].keys()).intersection(
                    set(self.sparse['platform groups'].keys()))

            if names_in_platforms_and_groups:
                msg = (
                    'Platforms and platform groups must not share names. '
                    'The following are in both sets:'
                )
                for name in names_in_platforms_and_groups:
                    msg += f'\n * {name}'
                raise GlobalConfigError(msg)

    def _expand_platforms(self):
        """Expand comma separated platform names.

        E.G. turn [platforms][foo, bar] into [platforms][foo] and
        platforms[bar].
        """
        if self.sparse.get('platforms'):
            self.sparse['platforms'] = expand_many_section(
                self.sparse['platforms']
            )

    def platform_dump(
        self,
        print_platform_names: bool = True,
        print_platforms: bool = True
    ) -> None:
        """Print informations about platforms currently defined.
        """
        if print_platform_names:
            self.dump_platform_names(self)
        if print_platforms:
            self.dump_platform_details(self)

    @staticmethod
    def dump_platform_names(cfg) -> None:
        """Print a list of defined platforms and groups.
        """
        # [platforms] is always defined with at least localhost
        platforms = '\n'.join(cfg.get(['platforms']).keys())
        print(f'{PLATFORM_REGEX_TEXT}\n\nPlatforms\n---------', file=stderr)
        print(platforms)
        try:
            platform_groups = '\n'.join(cfg.get(['platform groups']).keys())
        except ItemNotFoundError:
            return
        print('\nPlatform Groups\n--------------', file=stderr)
        print(platform_groups)

    @staticmethod
    def dump_platform_details(cfg) -> None:
        """Print platform and platform group configs.
        """
        for config in ['platforms', 'platform groups']:
            with suppress(ItemNotFoundError):
                printcfg({config: cfg.get([config], sparse=True)})
