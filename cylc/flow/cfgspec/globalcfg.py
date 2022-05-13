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
from sys import stderr
from typing import List, Optional, Tuple, Any

from contextlib import suppress
from pkg_resources import parse_version

from cylc.flow import LOG
from cylc.flow import __version__ as CYLC_VERSION
from cylc.flow.exceptions import GlobalConfigError
from cylc.flow.hostuserutil import get_user_home
from cylc.flow.network.client_factory import CommsMeth
from cylc.flow.parsec.config import (
    ConfigNode as Conf,
    ParsecConfig,
)
from cylc.flow.parsec.exceptions import ParsecError, ItemNotFoundError
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

TIMEOUT_DESCR = "Previously, 'timeout' was a stall timeout."
REPLACES = 'This item was previously called '


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

'''


# Event config descriptions shared between global and workflow config.
EVENTS_DESCR = {
    'startup handlers': (
        f'''
        :Default For: :cylc:conf:`flow.cylc \
        [scheduler][events]startup handlers`.

        Handlers to run at scheduler startup.

        .. versionchanged:: 8.0.0

           {REPLACES}``startup handler``.

        '''
    ),
    'shutdown handlers': (
        f'''
        :Default For: :cylc:conf:`flow.cylc \
        [scheduler][events]shutdown handlers`.

        Handlers to run at scheduler shutdown.

        .. versionchanged:: 8.0.0

           {REPLACES}``shutdown handler``.

        '''
    ),
    'abort handlers': (
        f'''
        :Default For: :cylc:conf:`flow.cylc[scheduler][events]abort handlers`.

        Handlers to run if the scheduler aborts.

        .. versionchanged:: 8.0.0

           {REPLACES}``aborted handler``.
        '''
    ),
    'workflow timeout': (
        f'''
        :Default For: :cylc:conf:`flow.cylc \
        [scheduler][events]workflow timeout`.

        Workflow timeout interval. The timer starts counting down at scheduler
        startup. It resets on workflow restart.

        .. versionadded:: 8.0.0

           {TIMEOUT_DESCR}
        '''
    ),
    'workflow timeout handlers': (
        f'''
        :Default For: :cylc:conf:`flow.cylc \
        [scheduler][events]workflow timeout handlers`.

        Handlers to run if the workflow timer times out.

        .. versionadded:: 8.0.0

           {TIMEOUT_DESCR}
        '''
    ),
    'abort on workflow timeout': (
        f'''
        :Default For: :cylc:conf:`flow.cylc \
        [scheduler][events]abort on workflow timeout`.

        Whether to abort if the workflow timer times out.

        .. versionadded:: 8.0.0

           {TIMEOUT_DESCR}
        '''
    ),
    'stall handlers': (
        f'''
        :Default For: :cylc:conf:`flow.cylc[scheduler][events]stall handlers`.

        Handlers to run if the scheduler stalls.

        .. versionchanged:: 8.0.0

           {REPLACES}``stalled handler``.
        '''
    ),
    'stall timeout': (
        f'''
        :Default For: :cylc:conf:`flow.cylc[scheduler][events]stall timeout`.

        The length of a timer which starts if the scheduler stalls.

        .. versionadded:: 8.0.0

           {TIMEOUT_DESCR}
        '''
    ),
    'stall timeout handlers': (
        f'''
        :Default For: :cylc:conf:`flow.cylc \
        [scheduler][events]stall timeout handlers`.

        Handlers to run if the stall timer times out.

        .. versionadded:: 8.0.0

           {TIMEOUT_DESCR}
        '''
    ),
    'abort on stall timeout': (
        f'''
        :Default For: :cylc:conf:`flow.cylc \
        [scheduler][events]abort on stall timeout`.

        Whether to abort if the stall timer times out.

        .. versionadded:: 8.0.0

           {TIMEOUT_DESCR}
        '''
    ),
    'inactivity timeout': (
        f'''
        :Default For: :cylc:conf:`flow.cylc \
        [scheduler][events]inactivity timeout`.

        Scheduler inactivity timeout interval. The timer resets when any
        workflow activity occurs.

        .. versionchanged:: 8.0.0

           {REPLACES} ``inactivity``.
        '''
    ),
    'inactivity timeout handlers': (
        f'''
        :Default For: :cylc:conf:`flow.cylc \
        [scheduler][events]inactivity timeout handlers`.

        Handlers to run if the inactivity timer times out.

        .. versionchanged:: 8.0.0

           {REPLACES}``inactivity handler``.
        '''
    ),
    'abort on inactivity timeout': (
        f'''
        :Default For: :cylc:conf:`flow.cylc \
        [scheduler][events]abort on inactivity timeout`.

        Whether to abort if the inactivity timer times out.

        .. versionchanged:: 8.0.0

           {REPLACES}``abort on inactivity``.
        '''
    )
}


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
    with Conf('scheduler', desc=f'''
        :Defaults For: :cylc:conf:`flow.cylc[scheduler]`

        .. versionchanged:: 8.0.0

           {REPLACES}``[cylc]``.

        .. note::

           :cylc:conf:`global.cylc[scheduler]` should not be confused with
           :cylc:conf:`flow.cylc[scheduling]`.
    '''):
        Conf('UTC mode', VDR.V_BOOLEAN, False, desc='''
            :Default For: :cylc:conf:`flow.cylc[scheduler]UTC mode`.
        ''')
        Conf('process pool size', VDR.V_INTEGER, 4, desc='''
            Maximum number of concurrent processes used to execute external job
            submission, event handlers, and job poll and kill commands

            .. versionchanged:: 8.0.0

               Moved into the ``[scheduler]`` section from the top level.

            .. seealso::

                :ref:`Managing External Command Execution`.

        ''')
        Conf('process pool timeout', VDR.V_INTERVAL, DurationFloat(600),
             desc='''
            After this interval Cylc will kill long running commands in the
            process pool.

            .. versionchanged:: 8.0.0

               Moved into the ``[scheduler]`` section from the top level.

            .. seealso::

               :ref:`Managing External Command Execution`.

            .. note::
               The default is set quite high to avoid killing important
               processes when the system is under load.
        ''')
        Conf('auto restart delay', VDR.V_INTERVAL, desc=f'''
            Maximum number of seconds the auto-restart mechanism will delay
            before restarting workflows.

            .. versionchanged:: 8.0.0

               {REPLACES}``global.rc[suite servers]auto restart delay``.

            When a host is set to automatically
            shutdown/restart it waits a random period of time
            between zero and ``auto restart delay`` seconds before
            beginning the process. This is to prevent large numbers of
            workflows from restarting simultaneously.

            .. seealso::

               :ref:`auto-stop-restart`

        ''')
        with Conf('run hosts', desc=f'''
            Configure workflow hosts and ports for starting workflows.

            .. versionchanged:: 8.0.0

               {REPLACES}``[suite servers]``.

            Additionally configure host selection settings specifying how to
            determine the most suitable run host at any given time from those
            configured.
        '''):
            Conf('available', VDR.V_SPACELESS_STRING_LIST, desc=f'''
                A list of workflow run hosts.

                .. versionchanged:: 8.0.0

                   {REPLACES}``[suite servers]run hosts``.

               Cylc will choose one of these hosts for a workflow to start on.
               (Unless an explicit host is provided as an option to the
               ``cylc play --host=<myhost>`` command.)
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

                .. versionchanged:: 8.0.0

                   {REPLACES}``[suite servers]condemned hosts``.

                If workflows are already running on
                condemned hosts, Cylc will shut them down and
                restart them on different hosts.

                .. seealso::

                   :ref:`auto-stop-restart`
            ''')
            Conf('ranking', VDR.V_STRING, desc=f'''
                Rank and filter run hosts based on system information.

                .. versionchanged:: 8.0.0

                   {REPLACES}``[suite servers][run host select]rank``.

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
            ''')

        with Conf('host self-identification', desc=f'''
            How Cylc determines and shares the identity of the workflow host.

            .. versionchanged:: 8.0.0

               {REPLACES}``[suite host self-identification]``.

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
                desc=f'''
                    Determines how cylc finds the identity of the
                    workflow host.

                    .. versionchanged:: 8.0.0

                       {REPLACES}``[suite host self-identification]``.

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

        with Conf('events', desc='''
            :Defaults For: :cylc:conf:`flow.cylc[scheduler][events]`.
        '''):
            Conf('handlers', VDR.V_STRING_LIST, desc='''
                :Default For: :cylc:conf:`flow.cylc \
                [scheduler][events]handlers`.
            ''')
            Conf('handler events', VDR.V_STRING_LIST, desc='''
                :Default For: :cylc:conf:`flow.cylc \
                [scheduler][events]handler events`.
            ''')
            Conf('mail events', VDR.V_STRING_LIST, desc='''
                Default for :cylc:conf:`flow.cylc \
                [scheduler][events]mail events`.
            ''')

            for item, desc in EVENTS_DESCR.items():
                if item.endswith("handlers"):
                    Conf(item, VDR.V_STRING_LIST, desc=desc)

                elif item.startswith("abort on"):
                    default = (item == "abort on stall timeout")
                    Conf(item, VDR.V_BOOLEAN, default, desc=desc)

                elif item.endswith("timeout"):
                    if item == "stall timeout":
                        def_intv: Optional['DurationFloat'] = (
                            DurationFloat(3600))
                    else:
                        def_intv = None
                    Conf(item, VDR.V_INTERVAL, def_intv, desc=desc)

        with Conf('mail', desc=f'''
            :Defaults For: :cylc:conf:`flow.cylc[scheduler][mail]`.

            Options for email handling.

            .. versionchanged:: 8.0.0

               {REPLACES}``[cylc][events]mail <item>``.
        '''):
            Conf('from', VDR.V_STRING, desc='''
                :Default For: :cylc:conf:`flow.cylc[scheduler][mail]from`.
            ''')
            Conf('smtp', VDR.V_STRING)
            Conf('to', VDR.V_STRING, desc='''
                :Default For: :cylc:conf:`flow.cylc[scheduler][mail]to`.
            ''')
            Conf('footer', VDR.V_STRING, desc='''
                :Default For: :cylc:conf:`flow.cylc[scheduler][mail]footer`.
            ''')
            Conf(
                'task event batch interval',
                VDR.V_INTERVAL,
                DurationFloat(300),
                desc='''
                    :Default For: :cylc:conf:`flow.cylc \
                    [scheduler][mail]task event batch interval`

                    .. versionchanged:: 8.0.0

                       This item was previously
                       ``[cylc]task event mail interval``
                '''
            )

        with Conf('main loop', desc='''
            :Defaults For: :cylc:conf:`flow.cylc[scheduler][main loop]`.

            Configuration of the Cylc Scheduler's main loop.

            .. versionadded:: 8.0.0
        '''):
            Conf('plugins', VDR.V_STRING_LIST,
                 ['health check', 'reset bad hosts'],
                 desc='''
                     Configure the default main loop plugins to use when
                     starting new workflows.

                     .. versionadded:: 8.0.0
            ''')

            with Conf('<plugin name>', desc='''
                Configure a main loop plugin.
            ''') as MainLoopPlugin:
                Conf('interval', VDR.V_INTERVAL, desc='''
                    :Default For: :cylc:conf:`flow.cylc \
                    [scheduler][main loop][<plugin name>]interval`.

                    The interval with which this plugin is run.

                    .. versionadded:: 8.0.0
                ''')

            with Conf('health check', meta=MainLoopPlugin, desc='''
                Checks the integrity of the workflow run directory.

                .. versionadded:: 8.0.0
            '''):
                Conf('interval', VDR.V_INTERVAL, DurationFloat(600), desc='''
                    The interval with which this plugin is run.

                    .. versionadded:: 8.0.0
                ''')

            with Conf('reset bad hosts', meta=MainLoopPlugin, desc='''
                Periodically clear the scheduler list of unreachable (bad)
                hosts.

                .. versionadded:: 8.0.0
            '''):
                Conf('interval', VDR.V_INTERVAL, DurationFloat(1800), desc='''
                    How often (in seconds) to run this plugin.

                    .. versionadded:: 8.0.0
                ''')

        with Conf('logging', desc=f'''
            Settings for the workflow event log.

            The workflow event log, held under the workflow run directory, is
            maintained as a rolling archive. Logs are rolled over (backed up
            and started anew) when they reach a configurable limit size.

            .. versionchanged:: 8.0.0

               {REPLACES}``[suite logging]``.
        '''):
            Conf('rolling archive length', VDR.V_INTEGER, 5, desc='''
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
            with Conf('<install target>'):
                Conf('run', VDR.V_STRING, None, desc="""
                    Alternative location for the run dir.

                    If specified, the workflow run directory will
                    be created in ``<this-path>/cylc-run/<workflow-name>``
                    and a symbolic link will be created from
                    ``$HOME/cylc-run/<workflow-name>``.
                    If not specified the workflow run directory will be created
                    in ``$HOME/cylc-run/<workflow-name>``.
                    All the workflow files and the ``.service`` directory get
                    installed into this directory.

                    .. versionadded:: 8.0.0
                """)
                Conf('log', VDR.V_STRING, None, desc="""
                    Alternative location for the log dir.

                    If specified the workflow log directory will be created in
                    ``<this-path>/cylc-run/<workflow-name>/log`` and a
                    symbolic link will be created from
                    ``$HOME/cylc-run/<workflow-name>/log``. If not specified
                    the workflow log directory will be created in
                    ``$HOME/cylc-run/<workflow-name>/log``.

                    .. versionadded:: 8.0.0
                """)
                Conf('share', VDR.V_STRING, None, desc="""
                    Alternative location for the share dir.

                    If specified the workflow share directory will be
                    created in ``<this-path>/cylc-run/<workflow-name>/share``
                    and a symbolic link will be created from
                    ``<$HOME/cylc-run/<workflow-name>/share``. If not specified
                    the workflow share directory will be created in
                    ``$HOME/cylc-run/<workflow-name>/share``.

                    .. versionadded:: 8.0.0
                """)
                Conf('share/cycle', VDR.V_STRING, None, desc="""
                    Alternative directory for the share/cycle dir.

                    If specified the workflow share/cycle directory
                    will be created in
                    ``<this-path>/cylc-run/<workflow-name>/share/cycle``
                    and a symbolic link will be created from
                    ``$HOME/cylc-run/<workflow-name>/share/cycle``. If not
                    specified the workflow share/cycle directory will be
                    created in ``$HOME/cylc-run/<workflow-name>/share/cycle``.

                    .. versionadded:: 8.0.0
                """)
                Conf('work', VDR.V_STRING, None, desc="""
                    Alternative directory for the work dir.

                    If specified the workflow work directory will be created in
                    ``<this-path>/cylc-run/<workflow-name>/work`` and a
                    symbolic link will be created from
                    ``$HOME/cylc-run/<workflow-name>/work``. If not specified
                    the workflow work directory will be created in
                    ``$HOME/cylc-run/<workflow-name>/work``.

                    .. versionadded:: 8.0.0
                """)

    with Conf('editors', desc='''
        Choose your favourite text editor for editing workflow configurations.
    '''):
        Conf('terminal', VDR.V_STRING, desc='''
            An in-terminal text editor to be used by the Cylc command line.

            If unspecified Cylc will use the environment variable
            ``$EDITOR`` which is the preferred way to set your text editor.

            .. Note::

                You can set your ``$EDITOR`` in your shell profile file
                (e.g. ``~.bashrc``)

            If neither this or ``$EDITOR`` are specified then Cylc will
            default to ``vi``.

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

            .. Note::

               You can set your ``$GEDITOR`` in your shell profile file
               (e.g. ``~.bashrc``)

            If neither this or ``$GEDITOR`` are specified then Cylc will
            default to ``gvim -fg``.

            Examples::

               atom --wait
               code --new-window --wait
               emacs
               gedit -s
               gvim -fg
               nedit
        ''')

    with Conf('platforms', desc='''
        Platforms allow you to define compute resources available at your
        site.

        .. versionadded:: 8.0.0

        A platform consists of a group of one or more hosts which share a
        file system and a job runner (batch system).

        A platform must allow interaction with the same task job from *any*
        of its hosts.
    '''):
        with Conf('<platform name>', desc='''
            Configuration defining a platform.

            .. versionadded:: 8.0.0

               Many of the items in platform definitions have been moved from
               ``flow.cylc[runtime][<namespace>][job]`` and
               ``flow.cylc[runtime][<namespace>][remote]``

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

        ''') as Platform:
            with Conf('meta', desc=PLATFORM_META_DESCR):
                Conf('<custom metadata>', VDR.V_STRING, '', desc='''
                    Any user-defined metadata item.
                ''')
            Conf('hosts', VDR.V_STRING_LIST, desc='''
                A list of hosts from which the job host can be selected using
                :cylc:conf:`[..][selection]method`.

                .. versionadded:: 8.0.0

                All hosts should share a file system.
            ''')
            Conf('job runner', VDR.V_STRING, 'background', desc=f'''
                The batch system/job submit method used to run jobs on the
                platform.

                .. versionchanged:: 8.0.0

                   {REPLACES}
                   ``suite.rc[runtime][<namespace>][job]batch system``.

                Examples:

                 * ``background``
                 * ``slurm``
                 *  ``pbs``

                .. seealso::

                   :ref:`List of built-in Job Runners <AvailableMethods>`
            ''')
            Conf('job runner command template', VDR.V_STRING, desc=f'''
                Set the command used by the chosen job runner.

                .. versionchanged:: 8.0.0

                   {REPLACES}``suite.rc[runtime][<namespace>][job]
                   batch system command template``.

                The template's ``%(job)s`` will be
                substituted by the job file path.
            ''')
            Conf('shell', VDR.V_STRING, '/bin/bash', desc='''

                .. versionchanged:: 8.0.0

                   Moved from ``suite.rc[runtime][<namespace>]job``.

            ''')
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
            Conf('submission polling intervals',
                 VDR.V_INTERVAL_LIST,
                 [DurationFloat(900)],
                 desc='''
                List of intervals at which to poll status of job submission.

                This config item is the default for
                :cylc:conf:`flow.cylc[runtime][<namespace>]
                submission polling intervals`.
            ''')
            Conf('submission retry delays', VDR.V_INTERVAL_LIST, None,
                 desc='''
                Cylc can automatically resubmit jobs after submission failures.

                This config item is the default for
                :cylc:conf:`flow.cylc[runtime][<namespace>]
                submission retry delays`
            ''')
            Conf('execution polling intervals',
                 VDR.V_INTERVAL_LIST,
                 [DurationFloat(900)],
                 desc='''
                List of intervals at which to poll status of job execution.

                Default for :cylc:conf:`flow.cylc[runtime][<namespace>]
                execution polling intervals`.
            ''')
            Conf('execution time limit polling intervals',
                 VDR.V_INTERVAL_LIST,
                 [DurationFloat(60), DurationFloat(120), DurationFloat(420)],
                 desc='''
                List of intervals after execution time limit to poll jobs.

                If a job exceeds its execution time limit, Cylc can poll
                more frequently to detect the expected job completion quickly.
                The last interval in the list is used repeatedly until the job
                completes.
                Multipliers can be used as shorthand as in the example below.

                Example::

                   5*PT2M, PT5M
            ''')
            Conf('ssh command',
                 VDR.V_STRING,
                 'ssh -oBatchMode=yes -oConnectTimeout=10',
                 desc='''
                A communication command used to invoke commands on this
                platform.

                Not used on the workflow host unless you run local tasks
                under another user account.  The value is assumed to be ``ssh``
                with some initial options or a command that implements a
                similar interface to ``ssh``.
            ''')
            Conf('rsync command',
                 VDR.V_STRING,
                 'rsync',
                 desc='''
                Command used for remote file installation. This supports POSIX
                compliant rsync implementation e.g. GNU or BSD.
            ''')
            Conf('use login shell', VDR.V_BOOLEAN, True, desc='''
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
            ''')
            Conf('cylc path', VDR.V_STRING, desc='''
                The path containing the ``cylc`` executable on a remote
                platform.

                .. versionchanged:: 8.0.0

                   Moved from ``suite.rc[runtime][<namespace>][job]
                   cylc executable``.

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
            ''')
            Conf('copyable environment variables', VDR.V_STRING_LIST, '',
                 desc='''
                A list containing the names of the environment variables to
                be copied from the scheduler to a job.
            ''')
            Conf('retrieve job logs', VDR.V_BOOLEAN, desc='''
                Global default for
                :cylc:conf:`flow.cylc[runtime][<namespace>][remote]
                retrieve job logs`.
            ''')
            Conf('retrieve job logs command', VDR.V_STRING, 'rsync -a',
                 desc='''
                If ``rsync -a`` is unavailable or insufficient to retrieve job
                logs from a remote platform, you can use this setting to
                specify a suitable command.
            ''')
            Conf('retrieve job logs max size', VDR.V_STRING, desc='''
                Global default for
                :cylc:conf:`flow.cylc[runtime][<namespace>][remote]
                retrieve job logs max size` for this platform.
            ''')
            Conf('retrieve job logs retry delays', VDR.V_INTERVAL_LIST,
                 desc='''
                Global default for
                :cylc:conf:`flow.cylc[runtime][<namespace>][remote]
                retrieve job logs retry delays`
                for this platform.
            ''')
            Conf('tail command template',
                 VDR.V_STRING, 'tail -n +1 -F %(filename)s', desc='''
                A command template (with ``%(filename)s`` substitution) to
                tail-follow job logs this platform, by ``cylc cat-log``.

                You are are unlikely to need to override this.
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
                For example, if Platform_A shares a file system with localhost:

                .. code-block:: cylc

                   [platforms]
                       [[Platform_A]]
                           install target = localhost
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
                this is not the default behavior because it prevents
                local task jobs from running, unless ``$PATH`` contains the
                ``cylc`` wrapper script.

                Specific environment variables can be singled out to pass
                through to the clean environment, if necessary.

                A standard set of executable paths is passed through to clean
                environments, and can be added to if necessary.
            ''')

            Conf('job submission environment pass-through', VDR.V_STRING_LIST,
                 desc='''
                List of environment variable names to pass through to
                job submission subprocesses.

                ``$HOME`` is passed automatically.

                You are unlikely to need this.
            ''')
            Conf('job submission executable paths', VDR.V_STRING_LIST,
                 desc=f'''
                Additional executable locations to pass to the job
                submission subprocess beyond the standard locations
                {", ".join(f"``{i}``" for i in SYSPATH)}.
                You are unlikely to need this.
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
            with Conf('selection', desc='''
                How to select platform from list of hosts.

                .. versionadded:: 8.0.0
            ''') as Selection:
                Conf('method', VDR.V_STRING, default='random',
                     options=['random', 'definition order'],
                     desc='''
                    Method for choosing the job host from the platform.

                    .. versionadded:: 8.0.0

                    .. rubric:: Available options

                    - ``random``: Choose randomly from the list of hosts.
                      This is suitable for a pool of identical hosts.
                    - ``definition order``: Take the first host in the list
                      unless that host was unreachable. In many cases
                      this is likely to cause load imbalances, but might
                      be appropriate if following the pattern
                      ``hosts = main, backup, failsafe``.
                ''')
        with Conf('localhost', meta=Platform, desc='''
            A default platform defining settings for jobs to be run on the
            same host as the workflow scheduler.

            .. attention::

               It is common practice to run the Cylc scheduler on a dedicated
               host: In this case **"localhost" will refer to the host where
               the scheduler is running and not the computer where you
               ran "cylc play"**.
        '''):
            Conf('hosts', VDR.V_STRING_LIST, ['localhost'])
            with Conf('selection', meta=Selection):
                Conf('method', VDR.V_STRING, default='definition order')

    # Platform Groups
    with Conf('platform groups', desc='''
        Platform groups allow you to group together platforms which would
        all be suitable for a given job.

        .. versionadded:: 8.0.0

        When Cylc sets up a task job it will pick a platform from a group.
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
    '''):  # noqa: SIM117 (keep same format)
        with Conf('<group>'):
            with Conf('meta', desc=PLATFORM_META_DESCR):
                Conf('<custom metadata>', VDR.V_STRING, '', desc='''
                    Any user-defined metadata item.
                ''')
            Conf('platforms', VDR.V_STRING_LIST, desc='''
                A list of platforms which can be selected if
                :cylc:conf:`flow.cylc[runtime][<namespace>]platform` matches
                the name of this platform group.

                .. versionadded:: 8.0.0
            ''')
            with Conf('selection'):
                Conf(
                    'method', VDR.V_STRING, default='random',
                    options=['random', 'definition order'],
                    desc='''
                        Method for selecting platform from group.

                        .. versionadded:: 8.0.0

                        options:

                        - random: Suitable for an identical pool of platforms.
                        - definition order: Pick the first available platform
                          from the list.
                    '''
                )
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
        else:
            # Use default locations.
            for conf_type, conf_dir in self.conf_dir_hierarchy:
                fname = os.path.join(conf_dir, self.CONF_BASENAME)
                try:
                    self._load(fname, conf_type)
                except ParsecError:
                    LOG.error(f'bad {conf_type} {fname}')
                    raise

        self._set_default_editors()
        self._no_platform_group_name_overlap()
        self._expand_platforms()

    def _set_default_editors(self):
        # default to $[G]EDITOR unless an editor is defined in the config
        # NOTE: use `or` to handle cases where an env var is set to ''
        cfg = self.get()
        if not cfg['editors']['terminal']:
            cfg['editors']['terminal'] = os.environ.get('EDITOR') or 'vi'
        if not cfg['editors']['gui']:
            cfg['editors']['gui'] = os.environ.get('GEDITOR') or 'gvim -fg'

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
            with suppress(ItemNotFoundError):
                self.dump_platform_names(self)
        if print_platforms:
            with suppress(ItemNotFoundError):
                self.dump_platform_details(self)

    @staticmethod
    def dump_platform_names(cfg) -> None:
        """Print a list of defined platforms and groups.
        """
        platforms = '\n'.join(cfg.get(['platforms']).keys())
        platform_groups = '\n'.join(cfg.get(['platform groups']).keys())
        print(f'{PLATFORM_REGEX_TEXT}\n\nPlatforms\n---------', file=stderr)
        print(platforms)
        print('\n\nPlatform Groups\n--------------', file=stderr)
        print(platform_groups)

    @staticmethod
    def dump_platform_details(cfg) -> None:
        """Print platform and platform group configs.
        """
        for config in ['platforms', 'platform groups']:
            printcfg({config: cfg.get([config], sparse=True)})
