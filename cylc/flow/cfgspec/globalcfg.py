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
from typing import List, Optional, Tuple, Any

from pkg_resources import parse_version

from cylc.flow import LOG
from cylc.flow import __version__ as CYLC_VERSION
from cylc.flow.hostuserutil import get_user_home
from cylc.flow.network.client_factory import CommsMeth
from cylc.flow.parsec.config import ParsecConfig, ConfigNode as Conf
from cylc.flow.parsec.exceptions import ParsecError
from cylc.flow.parsec.upgrade import upgrader
from cylc.flow.parsec.validate import (
    DurationFloat, CylcConfigValidator as VDR, cylc_config_validate)

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


with Conf('global.cylc', desc='''
    The global configuration which defines default Cylc Flow settings
    for a user or site.

    To view your global config run::

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

    .. note::

       Prior to Cylc 8, ``global.cylc`` was named ``global.rc``, but that name
       is no longer supported.
''') as SPEC:
    with Conf('scheduler', desc='''
        Default values for entries in :cylc:conf:`flow.cylc[scheduler]`
        section. This should not be confused with scheduling in the
        ``flow.cylc`` file.
    '''):
        Conf('UTC mode', VDR.V_BOOLEAN, False, desc='''
            Default for :cylc:conf:`flow.cylc[scheduler]UTC mode`.
        ''')
        Conf('process pool size', VDR.V_INTEGER, 4, desc='''
            Maximum number of concurrent processes used to execute external job
            submission, event handlers, and job poll and kill commands - see
            :ref:`Managing External Command Execution`.
        ''')
        Conf('process pool timeout', VDR.V_INTERVAL, DurationFloat(600),
             desc='''
            Interval after which long-running commands in the process pool
            will be killed - see :ref:`Managing External Command Execution`.

            .. note::
               The default is set quite high to avoid killing important
               processes when the system is under load.
        ''')
        Conf('auto restart delay', VDR.V_INTERVAL, desc='''
            Relates to Cylc's auto stop-restart mechanism (see
            :ref:`auto-stop-restart`).  When a host is set to automatically
            shutdown/restart it will first wait a random period of time
            between zero and ``auto restart delay`` seconds before
            beginning the process. This is to prevent large numbers of
            workflows from restarting simultaneously.
        ''')
        with Conf('run hosts', desc='''
            Configure workflow hosts and ports for starting workflows.
            Additionally configure host selection settings specifying how to
            determine the most suitable run host at any given time from those
            configured.
        '''):
            Conf('available', VDR.V_SPACELESS_STRING_LIST, desc='''
                A list of workflow run hosts. One of these hosts will be
                appointed for a workflow to start on if an explicit host is not
                provided as an option to the ``cylc play`` command.
            ''')
            Conf('ports', VDR.V_INTEGER_LIST, list(range(43001, 43101)),
                 desc='''
                A list of allowed ports for Cylc to use to run workflows.
            ''')
            Conf('condemned', VDR.V_ABSOLUTE_HOST_LIST, desc='''
                Hosts specified in ``condemned hosts`` will not be considered
                as workflow run hosts. If workflows are already running on
                ``condemned hosts`` they will be automatically shutdown and
                restarted (see:ref:`auto-stop-restart`).
            ''')
            Conf('ranking', VDR.V_STRING, desc='''
                Rank and filter run hosts based on system information.

                This can be used to provide load balancing to ensure no one run
                host is overloaded and provide thresholds beyond which Cylc
                will not attempt to start new schedulers on a host.

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
                   virtual_memory.available > 1000000000

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
            ''')

        with Conf('host self-identification', desc='''
            The workflow host's identity must be determined locally by cylc and
            passed to running tasks (via ``$CYLC_WORKFLOW_HOST``) so that task
            messages can target the right workflow on the right host.
        '''):
            # TODO
            # Is it conceivable that different remote task hosts at the same
            # site might see the workflow host differently? If so we'd need to
            # be able to override the target in workflow configurations.
            Conf(
                'method', VDR.V_STRING, 'name',
                options=['name', 'address', 'hardwired'],
                desc='''
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
            ''')
            Conf('target', VDR.V_STRING, 'google.com', desc='''
                This item is required for the *address* self-identification
                method. If your workflow host sees the internet, a common
                address such as ``google.com`` will do; otherwise choose a host
                visible on your intranet.
            ''')
            Conf('host', VDR.V_STRING, desc='''
                Use this item to explicitly set the name or IP address of the
                workflow host if you have to use the *hardwired*
                self-identification method.
            ''')

        with Conf('events', desc='''
            You can define site defaults for each of the following options,
            details of which can be found under
            :cylc:conf:`flow.cylc[scheduler][events]`.
        '''):
            Conf('handlers', VDR.V_STRING_LIST)
            Conf('handler events', VDR.V_STRING_LIST)
            Conf('mail events', VDR.V_STRING_LIST)
            Conf('startup handler', VDR.V_STRING_LIST)
            Conf('timeout handler', VDR.V_STRING_LIST)
            Conf('inactivity handler', VDR.V_STRING_LIST)
            Conf('shutdown handler', VDR.V_STRING_LIST)
            Conf('aborted handler', VDR.V_STRING_LIST)
            Conf('stalled handler', VDR.V_STRING_LIST)
            Conf('timeout', VDR.V_INTERVAL)
            Conf('inactivity', VDR.V_INTERVAL)
            Conf('abort on timeout', VDR.V_BOOLEAN)
            Conf('abort on inactivity', VDR.V_BOOLEAN)
            Conf('abort on stalled', VDR.V_BOOLEAN)

        with Conf('mail', desc='''
            Options for email handling.
        '''):
            Conf('from', VDR.V_STRING)
            Conf('smtp', VDR.V_STRING)
            Conf('to', VDR.V_STRING)
            Conf('footer', VDR.V_STRING)
            Conf(
                'task event batch interval',
                VDR.V_INTERVAL,
                DurationFloat(300),
                desc='''
                    Default for
                    :cylc:conf:`flow.cylc
                    [scheduler][mail]task event batch interval`
                '''
            )

        with Conf('main loop', desc='''
            Configuration of the Cylc Scheduler's main loop.
        '''):
            Conf('plugins', VDR.V_STRING_LIST,
                 ['health check', 'prune flow labels', 'reset bad hosts'],
                 desc='''
                     Configure the default main loop plugins to use when
                     starting new workflows.
            ''')

            with Conf('<plugin name>', desc='''
                Configure a main loop plugin.
            ''') as MainLoopPlugin:
                Conf('interval', VDR.V_INTERVAL, desc='''
                    The interval with which this plugin is run.
                ''')

            with Conf('health check', meta=MainLoopPlugin, desc='''
                Checks the integrity of the workflow run directory.
            '''):
                Conf('interval', VDR.V_INTERVAL, DurationFloat(600), desc='''
                    The interval with which this plugin is run.
                ''')

            with Conf('prune flow labels', meta=MainLoopPlugin, desc='''
                Prune redundant flow labels.
            '''):
                Conf('interval', VDR.V_INTERVAL, DurationFloat(600), desc='''
                    The interval with which this plugin is run.
                ''')

            with Conf('reset bad hosts', meta=MainLoopPlugin, desc='''
                Periodically clear the scheduler list of unreachable (bad)
                hosts.
            '''):
                Conf('interval', VDR.V_INTERVAL, DurationFloat(1800), desc='''
                    How often (in seconds) to run this plugin.
                ''')

        with Conf('logging', desc='''
            The workflow event log, held under the workflow run directory, is
            maintained as a rolling archive. Logs are rolled over (backed up
            and started anew) when they reach a configurable limit size.
        '''):
            Conf('rolling archive length', VDR.V_INTEGER, 5, desc='''
                How many rolled logs to retain in the archive.
            ''')
            Conf('maximum size in bytes', VDR.V_INTEGER, 1000000, desc='''
                Workflow event logs are rolled over when they reach this
                file size.
            ''')

    with Conf('install'):
        Conf('source dirs', VDR.V_STRING_LIST, default=['~/cylc-src'], desc='''
            A list of paths where ``cylc install <flow_name>`` will look for
            a workflow of that name. All workflow source directories in these
            locations will also show up in the GUI, ready for installation.

            .. note::
               If workflow source directories of the same name exist in more
               than one of these paths, only the first one will be picked up.
        ''')
        # Symlink Dirs
        with Conf('symlink dirs',  # noqa: SIM117 (keep same format)
                  desc="""
            Configure alternate workflow run directory locations. Symlinks from
            the the standard ``$HOME/cylc-run`` locations will be created.
        """):
            with Conf('<install target>'):
                Conf('run', VDR.V_STRING, None, desc="""
                    If specified, the workflow run directory will
                    be created in ``<run dir>/cylc-run/<workflow-name>`` and a
                    symbolic link will be created from
                    ``$HOME/cylc-run/<workflow-name>``.
                    If not specified the workflow run directory will be created
                    in ``$HOME/cylc-run/<workflow-name>``.
                    All the workflow files and the ``.service`` directory get
                    installed into this directory.
                """)
                Conf('log', VDR.V_STRING, None, desc="""
                    If specified the workflow log directory will be created in
                    ``<log dir>/cylc-run/<workflow-name>/log`` and a symbolic
                    link will be created from
                    ``$HOME/cylc-run/<workflow-name>/log``. If not specified
                    the workflow log directory will be created in
                    ``$HOME/cylc-run/<workflow-name>/log``.
                """)
                Conf('share', VDR.V_STRING, None, desc="""
                    If specified the workflow share directory will be
                    created in ``<share dir>/cylc-run/<workflow-name>/share``
                    and a symbolic link will be created from
                    ``<$HOME/cylc-run/<workflow-name>/share``. If not specified
                    the workflow share directory will be created in
                    ``$HOME/cylc-run/<workflow-name>/share``.
                """)
                Conf('share/cycle', VDR.V_STRING, None, desc="""
                    If specified the workflow share/cycle directory
                    will be created in
                    ``<share/cycle dir>/cylc-run/<workflow-name>/share/cycle``
                    and a symbolic link will be created from
                    ``$HOME/cylc-run/<workflow-name>/share/cycle``. If not
                    specified the workflow share/cycle directory will be
                    created in ``$HOME/cylc-run/<workflow-name>/share/cycle``.
                """)
                Conf('work', VDR.V_STRING, None, desc="""
                    If specified the workflow work directory will be created in
                    ``<work dir>/cylc-run/<workflow-name>/work`` and a symbolic
                    link will be created from
                    ``$HOME/cylc-run/<workflow-name>/work``. If not specified
                    the workflow work directory will be created in
                    ``$HOME/cylc-run/<workflow-name>/work``.
                """)

    with Conf('editors', desc='''
        Choose your favourite text editor for editing workflow configurations.
    '''):
        Conf('terminal', VDR.V_STRING, desc='''
            An in-terminal text editor to be used by the cylc command line.

            If unspecified Cylc will use the environment variable
            ``$EDITOR`` which is the preferred way to set your text editor.

            If neither this or ``$EDITOR`` are specified then Cylc will
            default to ``vi``.

            .. Note::
               You can set your ``$EDITOR`` in your shell profile file
               (e.g. ``~.bashrc``)

            Examples::

               ed
               emacs -nw
               nano
               vi
        ''')
        Conf('gui', VDR.V_STRING, desc='''
            A graphical text editor to be used by cylc.

            If unspecified Cylc will use the environment variable
            ``$GEDITOR`` which is the preferred way to set your text editor.

            If neither this or ``$GEDITOR`` are specified then Cylc will
            default to ``gvim -fg``.

            .. Note::
               You can set your ``$GEDITOR`` in your shell profile file
               (e.g. ``~.bashrc``)

            Examples::

               atom --wait
               code --new-window --wait
               emacs
               gedit -s
               gvim -fg
               nedit
        ''')

    with Conf('platforms'):
        with Conf('<platform name>') as Platform:
            Conf('job runner', VDR.V_STRING, 'background', desc='''
                The batch system/job submit method used to run jobs on the
                platform, e.g., ``background``, ``at``, ``slurm``,
                ``loadleveler``...
            ''')
            Conf('job runner command template', VDR.V_STRING)
            Conf('shell', VDR.V_STRING, '/bin/bash')
            Conf('communication method',
                 VDR.V_STRING, 'zmq',
                 options=[meth.value for meth in CommsMeth], desc='''
                The means by which task progress messages are reported back to
                the running workflow.

                Options:

                zmq
                   Direct client-server TCP communication via network ports
                poll
                   The workflow polls for task status (no task messaging)
                ssh
                   Use non-interactive ssh for task communications
            ''')
            # TODO ensure that it is possible to over-ride the following three
            # settings in workflow config.
            Conf('submission polling intervals', VDR.V_INTERVAL_LIST, desc='''
                Cylc can also poll submitted jobs to catch problems that
                prevent the submitted job from executing at all, such as
                deletion from an external job runner queue. Routine
                polling is done only for the polling ``task communication
                method`` unless workflow-specific polling is configured in
                the workflow configuration. A list of interval values can be
                specified as for execution polling but a single value
                is probably sufficient for job submission polling.

                Example::

                   5*PT1M, 10*PT5M
            ''')
            Conf('submission retry delays', VDR.V_INTERVAL_LIST, None)
            Conf('execution polling intervals', VDR.V_INTERVAL_LIST, desc='''
                Cylc can poll running jobs to catch problems that prevent task
                messages from being sent back to the workflow, such as hard job
                kills, network outages, or unplanned task host shutdown.
                Routine polling is done only for the polling *task
                communication method* (below) unless polling is
                configured in the workflow configuration.  A list of interval
                values can be specified, with the last value used repeatedly
                until the task is finished - this allows more frequent polling
                near the beginning and end of the anticipated task run time.
                Multipliers can be used as shorthand as in the example below.

                Example::

                   5*PT1M, 10*PT5M
            ''')
            Conf('execution time limit polling intervals',
                 VDR.V_INTERVAL_LIST, desc='''
                The intervals between polling after a task job (submitted to
                the relevant job runner on the relevant host) exceeds its
                execution time limit. The default setting is PT1M, PT2M, PT7M.
                The accumulated times (in minutes) for these intervals will be
                roughly 1, 1 + 2 = 3 and 1 + 2 + 7 = 10 after a task job
                exceeds its execution time limit.
            ''')
            Conf('ssh command',
                 VDR.V_STRING,
                 'ssh -oBatchMode=yes -oConnectTimeout=10',
                 desc='''
                A string for the command used to invoke commands on this host.
                Not used on the workflow host unless you run local tasks
                under another user account.  The value is assumed to be ``ssh``
                with some initial options or a command that implements a
                similar interface to ``ssh``.
            ''')
            Conf('use login shell', VDR.V_BOOLEAN, True, desc='''
                Whether to use a login shell or not for remote command
                invocation. By default cylc runs remote ssh commands using a
                login shell:

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
            ''')
            Conf('hosts', VDR.V_STRING_LIST)
            Conf('cylc path', VDR.V_STRING, desc='''
                The path containing the ``cylc`` executable on a remote host.

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
            ''')
            Conf('global init-script', VDR.V_STRING, desc='''
                If specified, the value of this setting will be inserted to
                just before the ``init-script`` section of all job scripts that
                are to be submitted to the specified remote host.
            ''')
            Conf('copyable environment variables', VDR.V_STRING_LIST, '',
                 desc='''
                A list containing the names of the environment variables to
                be copied from the scheduler to a job.
            ''')
            Conf('retrieve job logs', VDR.V_BOOLEAN, desc='''
                Global default for
                :cylc:conf:`flow.cylc[runtime][<namespace>][remote]retrieve job
                logs`.
            ''')
            Conf('retrieve job logs command', VDR.V_STRING, 'rsync -a',
                 desc='''
                If ``rsync -a`` is unavailable or insufficient to retrieve job
                logs from a remote host, you can use this setting to specify a
                suitable command.
            ''')
            Conf('retrieve job logs max size', VDR.V_STRING, desc='''
                Global default for the
                :cylc:conf:`flow.cylc[runtime][<namespace>][remote]retrieve job
                logs max size`.
                the specified host.
            ''')
            Conf('retrieve job logs retry delays', VDR.V_INTERVAL_LIST,
                 desc='''
                Global default for the
                :cylc:conf:`flow.cylc[runtime][<namespace>][remote]retrieve job
                logs retry delays`.
                setting for the specified host.
            ''')
            Conf('tail command template',
                 VDR.V_STRING, 'tail -n +1 -F %(filename)s', desc='''
                A command template (with ``%(filename)s`` substitution) to
                tail-follow job logs on HOST, by ``cylc cat-log``. You are
                unlikely to need to override this.
            ''')
            Conf('err tailer', VDR.V_STRING, desc='''
                A command template (with ``%(job_id)s`` substitution) that can
                be used to tail-follow the stderr stream of a running job if
                SYSTEM does not use the normal log file location while the job
                is running.  This setting overrides
                :cylc:conf:`[..]tail command template`.

                Examples::

                   # for PBS
                   qcat -f -e %(job_id)s
            ''')
            Conf('out tailer', VDR.V_STRING, desc='''
                A command template (with ``%(job_id)s`` substitution) that can
                be used to tail-follow the stdout stream of a running job if
                SYSTEM does not use the normal log file location while the job
                is running.  This setting overrides
                :cylc:conf:`[..]tail command template`.

                Examples::

                   # for PBS
                   qcat -f -o %(job_id)s
            ''')
            Conf('err viewer', VDR.V_STRING, desc='''
                A command template (with ``%(job_id)s`` substitution) that can
                be used to view the stderr stream of a running job if SYSTEM
                does not use the normal log file location while the job is
                running.

                Examples::

                   # for PBS
                   qcat -e %(job_id)s
            ''')
            Conf('out viewer', VDR.V_STRING, desc='''
                A command template (with ``%(job_id)s`` substitution) that can
                be used to view the stdout stream of a running job if SYSTEM
                does not use the normal log file location while the job is
                running.

                Examples::

                   # for PBS
                   qcat -o %(job_id)s
            ''')
            Conf('job name length maximum', VDR.V_INTEGER, desc='''
                The maximum length for job name acceptable by a job runner on
                a given host.  Currently, this setting is only meaningful for
                PBS jobs. For example, PBS 12 or older will fail a job submit
                if the job name has more than 15 characters; whereas PBS 13
                accepts up to 236 characters.
            ''')
            Conf('install target', VDR.V_STRING, desc='''
                This defaults to the platform name. This will be used as the
                target for remote file installation.
                For example, to indicate to Cylc that Platform_A shares a file
                system with localhost, we would configure as follows:

                .. code-block:: cylc

                   [platforms]
                       [[Platform_A]]
                           install target = localhost
            ''')

            Conf('clean job submission environment', VDR.V_BOOLEAN, False,
                 desc='''
                Job submission subprocesses inherit their parent environment by
                default. So remote job submissions inherit the default
                non-interactive shell environment, but local ones inherit the
                scheduler environment. This means local jobs see the scheduler
                environment unless the local batch system prevents it, which
                can cause problems - e.g. scheduler ``$PYTHON...`` variables
                can affect Python programs executed by task job scripts. For
                consistent handling of local and remote jobs a clean job
                submission environment is recommended, but it is not the
                default because it prevents local task jobs from running unless
                the ``cylc`` version selection wrapper script is installed in
                ``$PATH`` (a clean environment prevents local jobs from seeing
                the scheduler's virtual environment).

                Specific environment variables can be singled out to pass
                through to the clean environment, if necessary.

                A standard set of executable paths is passed through to clean
                environments, and can be added to if necessary.
            ''')

            Conf('job submission environment pass-through', VDR.V_STRING_LIST,
                 desc='''
                Minimal list of environment variable names to pass through to
                job submission subprocesses. $HOME is passed automatically.
                You are unlikely to need this.
            ''')
            Conf('job submission executable paths', VDR.V_STRING_LIST, desc='''
                Additional executable locations to pass to the job
                submission subprocess beyond the standard locations''' +
                 ', '.join(SYSPATH) + '''. You are unlikely to need this.
            ''')
            Conf('max batch submit size', VDR.V_INTEGER, default=100, desc='''
                Limits the maximum number of jobs that can be submitted at
                once.

                Where possible Cylc will batch together job submissions to
                the same platform for efficiency. Submitting very large
                numbers of jobs can cause problems with some submission
                systems so for safety there is an upper limit on the number
                of job submissions which can be batched together.
            ''')
            with Conf('selection'):
                Conf(
                    'method', VDR.V_STRING, default='random',
                    options=['random', 'definition order'],
                    desc='''
                        Host selection method for the platform. Available
                        options:

                        - random: Suitable for an identical pool of hosts.
                        - definition order: Take the first host in the list
                          unless that host has been unreachable. In many cases
                          this is likely to cause load imbalances, but might
                          be appropriate if your hosts were
                          ``main, backup, failsafe``.
                    '''
                )
        with Conf('localhost', meta=Platform):
            Conf('hosts', VDR.V_STRING_LIST, ['localhost'])

    # Platform Groups
    with Conf('platform groups'):  # noqa: SIM117 (keep same format)
        with Conf('<group>'):
            Conf('platforms', VDR.V_STRING_LIST)
    # task
    with Conf('task events', desc='''
        Global site/user defaults for
        :cylc:conf:`flow.cylc[runtime][<namespace>][events]`.
    '''):
        Conf('execution timeout', VDR.V_INTERVAL)
        Conf('handlers', VDR.V_STRING_LIST)
        Conf('handler events', VDR.V_STRING_LIST)
        Conf('handler retry delays', VDR.V_INTERVAL_LIST, None)
        Conf('mail events', VDR.V_STRING_LIST)
        Conf('submission timeout', VDR.V_INTERVAL)

    with Conf('task mail', desc='''
        Global site/user defaults for
        :cylc:conf:`flow.cylc[runtime][<namespace>][mail]`.
    '''):
        Conf('from', VDR.V_STRING)
        Conf('to', VDR.V_STRING)


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
    smart_ver: Any = parse_version(version)
    # (No type anno. yet for Version in pkg_resources.extern.packaging.version)
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
    def get_inst(cls, cached=True):
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

    def _load(self, fname, conf_type):
        if os.access(fname, os.F_OK | os.R_OK):
            self.loadcfg(fname, conf_type)

    def load(self):
        """Load or reload configuration from files."""
        self.sparse.clear()
        self.dense.clear()
        LOG.debug("Loading site/user config files")
        conf_path_str = os.getenv("CYLC_CONF_PATH")
        if conf_path_str:
            # Explicit config file override.
            fname = os.path.join(conf_path_str, self.CONF_BASENAME)
            self._load(fname, upgrader.USER_CONFIG)
        elif conf_path_str is None:
            # Use default locations.
            for conf_type, conf_dir in self.conf_dir_hierarchy:
                fname = os.path.join(conf_dir, self.CONF_BASENAME)
                try:
                    self._load(fname, conf_type)
                except ParsecError as exc:
                    if conf_type == upgrader.SITE_CONFIG:
                        # Warn on bad site file (users can't fix it).
                        LOG.warning(
                            f'ignoring bad {conf_type} {fname}:\n{exc}')
                    else:
                        # Abort on bad user file (users can fix it).
                        LOG.error(f'bad {conf_type} {fname}')
                        raise

        self._set_default_editors()

    def _set_default_editors(self):
        # default to $[G]EDITOR unless an editor is defined in the config
        # NOTE: use `or` to handle cases where an env var is set to ''
        cfg = self.get()
        if not cfg['editors']['terminal']:
            cfg['editors']['terminal'] = os.environ.get('EDITOR') or 'vi'
        if not cfg['editors']['gui']:
            cfg['editors']['gui'] = os.environ.get('GEDITOR') or 'gvim -fg'
