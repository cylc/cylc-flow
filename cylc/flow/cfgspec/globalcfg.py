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
"""Cylc site and user configuration file spec."""

import os
import packaging.version

from cylc.flow import LOG
from cylc.flow import __version__ as CYLC_VERSION
from cylc.flow.hostuserutil import get_user_home
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
with Conf('global.cylc', desc='''
    The global configuration which defines default Cylc Flow settings
    for a user or site.

    To view your global config run::

       $ cylc get-global-config --sparse

    Cylc will attempt to load the global configuration (``global.cylc``) from a
    hierarchy of locations, including the site directory (defaults to
    ``/etc/cylc/flow/``) and the user directory (``~/.cylc/flow/``). E.g. for
    Cylc version 8.0.1, the hierarchy would be, in order of ascending priority:

    * ``${CYLC_SITE_CONF_PATH}/global.cylc``
    * ``${CYLC_SITE_CONF_PATH}/8/global.cylc``
    * ``${CYLC_SITE_CONF_PATH}/8.0/global.cylc``
    * ``${CYLC_SITE_CONF_PATH}/8.0.1/global.cylc``
    * ``~/.cylc/flow/global.cylc``
    * ``~/.cylc/flow/8/global.cylc``
    * ``~/.cylc/flow/8.0/global.cylc``
    * ``~/.cylc/flow/8.0.1/global.cylc``

    A setting in a file lower down in the list will override the same setting
    from those higher up (but if a setting is present in a file higher up and
    not in any files lower down, it will not be overridden).

    Setting the ``CYLC_SITE_CONF_PATH`` environment variable overrides the
    default value of ``/etc/cylc/flow/``.

    To override the entire hierarchy, set the ``CYLC_CONF_PATH`` environment
    variable to the directory containing your ``global.cylc`` file.

    .. note::

       The ``global.cylc`` file can be templated using Jinja2 variables.
       See :ref:`Jinja`.

    .. note::

       Prior to Cylc 8, ``global.cylc`` was named ``global.rc``, but that name
       is no longer supported.
''') as SPEC:

    # suite
    Conf('process pool size', VDR.V_INTEGER, 4, desc='''
        Maximum number of concurrent processes used to execute external job
        submission, event handlers, and job poll and kill commands - see
        :ref:`Managing External Command Execution`.
    ''')
    Conf('process pool timeout', VDR.V_INTERVAL, DurationFloat(600), desc='''
        Interval after which long-running commands in the process pool will be
        killed - see :ref:`Managing External Command Execution`.

        .. note::
           The default is set quite high to avoid killing important
           processes when the system is under load.
    ''')
    Conf('run directory rolling archive length', VDR.V_INTEGER, -1, desc='''
        The number of old run directory trees to retain at start-up.
    ''')

    with Conf('scheduler', desc='''
        Default values for entries in :cylc:conf:`flow.cylc[scheduler]`
        section. This should not be confused with scheduling in the
        ``flow.cylc`` file.
    '''):
        Conf('UTC mode', VDR.V_BOOLEAN, False, desc='''
                Default for :cylc:conf:`flow.cylc[scheduler]UTC mode`.
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
                    :cylc:conf:
                    `flow.cylc[scheduler][mail]task event batch interval`.
                '''
            )

        with Conf('main loop', desc='''
            Configuration of the Cylc Scheduler's main loop.
        '''):
            Conf('plugins', VDR.V_STRING_LIST,
                 ['health check', 'prune flow labels'], desc='''
                Configure the default main loop plugins to use when
                starting up new suites.
            ''')

            with Conf('<plugin name>', desc='''
                Configure a main loop plugin.
            ''') as MainLoopPlugin:
                Conf('interval', VDR.V_INTERVAL, desc='''
                    The interval with which this plugin is run.
                ''')

            with Conf('health check', meta=MainLoopPlugin, desc='''
                Checks the integrity of the suite run directory.
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

    with Conf('suite logging', desc='''
        The suite event log, held under the suite run directory, is maintained
        as a rolling archive. Logs are rolled over (backed up and started anew)
        when they reach a configurable limit size.
    '''):
        Conf('rolling archive length', VDR.V_INTEGER, 5, desc='''
            How many rolled logs to retain in the archive.
        ''')
        Conf('maximum size in bytes', VDR.V_INTEGER, 1000000, desc='''
            Suite event logs are rolled over when they reach this file size.
        ''')

    with Conf('editors', desc='''
        Choose your favourite text editor for editing suite configurations.
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
                code -nw
                emacs
                gedit -s
                gvim -fg
                nedit
        ''')

    with Conf('platforms'):
        with Conf('<platform name>') as Platform:
            Conf('batch system', VDR.V_STRING, 'background')
            Conf('batch submit command template', VDR.V_STRING)
            Conf('shell', VDR.V_STRING, '/bin/bash')
            Conf('run directory', VDR.V_STRING, '$HOME/cylc-run', desc='''
                The number of old run directory trees to retain at start-up.
            ''')
            Conf('work directory', VDR.V_STRING, '$HOME/cylc-run', desc='''
                The top level for suite work and share directories. Can contain
                ``$HOME`` or ``$USER`` but not other environment variables (the
                item cannot actually be evaluated by the shell on HOST before
                use, but the remote home directory is where ``rsync`` and
                ``ssh`` naturally land, and the remote username is known by the
                suite server program).

                Example::

                   /nfs/data/$USER/cylc-run
            ''')
            Conf('suite definition directory', VDR.V_STRING)
            Conf('communication method',
                 VDR.V_STRING, 'zmq', options=['zmq', 'poll'], desc='''
                The means by which task progress messages are reported back to
                the running suite.

                Options:

                zmq
                   Direct client-server TCP communication via network ports
                poll
                   The suite polls for the status of tasks (no task messaging)
            ''')
            # TODO ensure that it is possible to over-ride the following three
            # settings in suite config.
            Conf('submission polling intervals', VDR.V_INTERVAL_LIST, desc='''
                Cylc can also poll submitted jobs to catch problems that
                prevent the submitted job from executing at all, such as
                deletion from an external batch scheduler queue. Routine
                polling is done only for the polling ``task communication
                method`` unless suite-specific polling is configured in
                the suite configuration. A list of interval values can be
                specified as for execution polling but a single value
                is probably sufficient for job submission polling.

                Example::

                   5*PT1M, 10*PT5M
            ''')
            Conf('submission retry delays', VDR.V_INTERVAL_LIST, None)
            Conf('execution polling intervals', VDR.V_INTERVAL_LIST, desc='''
                Cylc can poll running jobs to catch problems that prevent task
                messages from being sent back to the suite, such as hard job
                kills, network outages, or unplanned task host shutdown.
                Routine polling is done only for the polling *task
                communication method* (below) unless suite-specific polling is
                configured in the suite configuration.  A list of interval
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
                the relevant batch system on the relevant host) exceeds its
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
                This is not used on the suite host unless you run local tasks
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

                which will source ``/etc/profile`` and ``~/.profile`` to set up
                the user environment.  However, for security reasons some
                institutions do not allow unattended commands to start login
                shells, so you can turn off this behaviour to get:

                .. code-block:: bash

                   ssh user@host 'cylc ...'

                which will use the default shell on the remote machine,
                sourcing ``~/.bashrc`` (or ``~/.cshrc``) to set up the
                environment.
            ''')
            Conf('hosts', VDR.V_STRING_LIST)
            Conf('cylc executable', VDR.V_STRING, 'cylc', desc='''
                The ``cylc`` executable on a remote host.

                .. note::

                   This should normally point to the cylc multi-version wrapper
                   on the host, not ``bin/cylc`` for a specific installed
                   version.

                Specify a full path if ``cylc`` is not in ``$PATH`` when it is
                invoked via ``ssh`` on this host.
            ''')
            Conf('global init-script', VDR.V_STRING, desc='''
                If specified, the value of this setting will be inserted to
                just before the ``init-script`` section of all job scripts that
                are to be submitted to the specified remote host.
            ''')
            Conf('copyable environment variables', VDR.V_STRING_LIST, '',
                 desc='''
                A list containing the names of the environment variables that
                can and/or need to be copied from the suite server program to a
                job.
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
                The maximum length for job name acceptable by a batch system on
                a given host.  Currently, this setting is only meaningful for
                PBS jobs. For example, PBS 12 or older will fail a job submit
                if the job name has more than 15 characters; whereas PBS 13
                accepts up to 236 characters.
            ''')
            Conf('owner', VDR.V_STRING)
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
            Conf('inherit')

        with Conf('localhost', meta=Platform):
            Conf('hosts', VDR.V_STRING_LIST, ['localhost'])

    # Platform Groups
    with Conf('platform groups'):
        with Conf('<group>'):
            Conf('platforms', VDR.V_STRING_LIST)
    # Symlink Dirs
    with Conf('symlink dirs'):
        with Conf('install target'):
            Conf('run', VDR.V_STRING, None, desc="""
                Specifies the directory where the workflow run directories are
                created. If specified, the workflow run directory will be
                created in <run dir>/<workflow-name> and a symbolic link will
                be created from $HOME/cylc-run/<workflow-name>.
                If not specified the workflow run directory will be created in
                $HOME/cylc-run/<workflow-name>.
                All the workflow files and the .service directory get installed
                into this directory.
            """)
            Conf('log', VDR.V_STRING, None, desc="""
                Specifies the directory where log directories are created. If
                specified the workflow log directory will be created in
                <log dir>/<workflow-name>/log and a symbolic link will be
                created from $HOME/cylc-run/<workflow-name>/log. If not
                specified the workflow log directory will be created in
                $HOME/cylc-run/<workflow-name>/log.
            """)
            Conf('share', VDR.V_STRING, None, desc="""
                Specifies the directory where share directories are created.
                If specified the workflow share directory will be created in
                <share dir>/<workflow-name>/share and a symbolic link will be
                created from <$HOME/cylc-run/<workflow-name>/share. If not
                specified the workflow share directory will be created in
                $HOME/cylc-run/<workflow-name>/share.
            """)
            Conf('share/cycle', VDR.V_STRING, None, desc="""
                Specifies the directory where share/cycle directories are
                created. If specified the workflow share/cycle directory will
                be created in <share/cycle dir>/<workflow-name>/share/cycle and
                a symbolic link will be created from
                $HOME/cylc-run/<workflow-name>/share/cycle.
                If not specified the workflow share/cycle directory will be
                created in $HOME/cylc-run/<workflow-name>/share/cycle.
            """)
            Conf('work', VDR.V_STRING, None, desc="""
                Specifies the directory where work directories are created.
                If specified the workflow work directory will be created in
                <work dir>/<workflow-name>/work and a symbolic link will be
                created from $HOME/cylc-run/<workflow-name>/work. If not
                specified the workflow work directory will be created in
                $HOME/cylc-run/<workflow-name>/work.
            """)
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
        Conf('retry delays', VDR.V_INTERVAL_LIST)
        Conf('smtp', VDR.V_STRING)
        Conf('to', VDR.V_STRING)

    # suite
    with Conf('suite host self-identification', desc='''
        The suite host's identity must be determined locally by cylc and passed
        to running tasks (via ``$CYLC_SUITE_HOST``) so that task messages can
        target the right suite on the right host.

        .. todo
           Is it conceivable that different remote task hosts at the same site
           might see the suite host differently? If so we would need to be able
           to override the target in suite configurations.
    '''):
        Conf('method', VDR.V_STRING, 'name',
             options=['name', 'address', 'hardwired'], desc='''
            This item determines how cylc finds the identity of the suite host.
            For the default *name* method cylc asks the suite host for its host
            name. This should resolve on remote task hosts to the IP address of
            the suite host; if it doesn't, adjust network settings or use one
            of the other methods. For the *address* method, cylc attempts to
            use a special external "target address" to determine the IP address
            of the suite host as seen by remote task hosts.  And finally, as a
            last resort, you can choose the *hardwired* method and manually
            specify the host name or IP address of the suite host.

            Options:

            name
               Self-identified host name.
            address
               Automatically determined IP address (requires *target*).
            hardwired
               Manually specified host name or IP address (requires *host*).
        ''')
        Conf('target', VDR.V_STRING, 'google.com', desc='''
            This item is required for the *address* self-identification method.
            If your suite host sees the internet, a common address such as
            ``google.com`` will do; otherwise choose a host visible on your
            intranet.
        ''')
        Conf('host', VDR.V_STRING, desc='''
            Use this item to explicitly set the name or IP address of the suite
            host if you have to use the *hardwired* self-identification method.
        ''')

    # suite
    with Conf('suite servers', desc='''
        Configure allowed suite hosts and ports for starting up (running or
        restarting) suites. Additionally configure host selection settings
        specifying how to determine the most suitable run host at any given
        time from those configured.
    '''):
        Conf('run hosts', VDR.V_SPACELESS_STRING_LIST, desc='''
            A list of allowed suite run hosts. One of these hosts will be
            appointed for a suite to start up on if an explicit host is not
            provided as an option to a ``run`` or ``restart`` command.
        ''')
        Conf('run ports', VDR.V_INTEGER_LIST, list(range(43001, 43101)),
             desc='''
            A list of allowed ports for Cylc to use to run suites.
        ''')
        Conf('condemned hosts', VDR.V_ABSOLUTE_HOST_LIST, desc='''
            Hosts specified in ``condemned hosts`` will not be considered as
            suite run hosts. If suites are already running on ``condemned
            hosts`` they will be automatically shutdown and restarted (see
            :ref:`auto-stop-restart`).
        ''')
        Conf('auto restart delay', VDR.V_INTERVAL, desc='''
            Relates to Cylc's auto stop-restart mechanism (see
            :ref:`auto-stop-restart`).  When a host is set to automatically
            shutdown/restart it will first wait a random period of time between
            zero and ``auto restart delay`` seconds before beginning the
            process. This is to prevent large numbers of suites from restarting
            simultaneously.
        ''')
        Conf('ranking', VDR.V_STRING)


def upg(cfg, descr):
    """Upgrader."""
    u = upgrader(cfg, descr)
    u.upgrade()


def get_version_hierarchy(version):
    """Return list of versions whose global configs are compatible, in
    ascending priority.

    Args:
        version (str): A PEP 440 compliant version number.

    Example:
        >>> get_version_hierarchy('8.0.1a2.dev')
        ['', '8', '8.0', '8.0.1', '8.0.1a2', '8.0.1a2.dev']

    """
    smart_ver = packaging.version.Version(version)
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
    Handle global (all suites) site and user configuration for cylc.
    User file values override site file values.
    """

    _DEFAULT = None
    _HOME = os.getenv('HOME') or get_user_home()
    CONF_BASENAME = "global.cylc"

    def __init__(self, *args, **kwargs):
        self.SITE_CONF_PATH = (os.getenv('CYLC_SITE_CONF_PATH') or
                               os.path.join(os.sep, 'etc', 'cylc', 'flow'))
        self.USER_CONF_PATH = os.path.join(self._HOME, '.cylc', 'flow')
        version_hierarchy = get_version_hierarchy(CYLC_VERSION)
        self.CONF_DIR_HIERARCHY = [
            *[(upgrader.SITE_CONFIG, os.path.join(self.SITE_CONF_PATH, ver))
              for ver in version_hierarchy],
            *[(upgrader.USER_CONFIG, os.path.join(self.USER_CONF_PATH, ver))
              for ver in version_hierarchy]
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

    def load(self):
        """Load or reload configuration from files."""
        self.sparse.clear()
        self.dense.clear()
        LOG.debug("Loading site/user config files")
        conf_path_str = os.getenv("CYLC_CONF_PATH")
        if conf_path_str:
            # Explicit config file override.
            fname = os.path.join(conf_path_str, self.CONF_BASENAME)
            if os.access(fname, os.F_OK | os.R_OK):
                self.loadcfg(fname, upgrader.USER_CONFIG)
        elif conf_path_str is None:
            # Use default locations.
            for conf_type, conf_dir in self.CONF_DIR_HIERARCHY:
                fname = os.path.join(conf_dir, self.CONF_BASENAME)
                if not os.access(fname, os.F_OK | os.R_OK):
                    continue
                try:
                    self.loadcfg(fname, conf_type)
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
