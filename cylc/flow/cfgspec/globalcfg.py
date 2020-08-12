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
import re

from cylc.flow import LOG
from cylc.flow import __version__ as CYLC_VERSION
from cylc.flow.hostuserutil import get_user_home, is_remote_user
from cylc.flow.network.authorisation import Priv
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
with Conf('flow.rc', desc='''
    The global configuration which defines default Cylc Flow settings
    for a user or site.

    To view your global config run::

       $ cylc get-global-config --sparse


    Cylc will attempt to load the global configuration (flow.rc) from two
    locations:

    * ``/etc/cylc/flow/<CYLC_VERSION>/flow.rc``
    * ``~/.cylc/flow/<CYLC_VERSION>/flow.rc``

    If both files are present files will be loaded in this order so those
    lower down the list may override settings from those higher up.

    To override the default configuration path use ``CYLC_CONF_PATH``.

    .. note::

       The ``flow.rc`` file can be templated using Jinja2 variables.
       See :ref:`Jinja`.
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
    # client
    Conf('disable interactive command prompts', VDR.V_BOOLEAN, True, desc='''
        Commands that intervene in running suites can be made to ask for
        confirmation before acting. Some find this annoying and ineffective as
        a safety measure, however, so command prompts are disabled by default.
    ''')
    # suite
    Conf('run directory rolling archive length', VDR.V_INTEGER, -1, desc='''
        The number of old run directory trees to retain at start-up.
    ''')

    # suite
    with Conf('cylc', desc='''
        Default values for entries in the suite.rc ``[cylc]`` section.
    '''):
        Conf('UTC mode', VDR.V_BOOLEAN, False, desc='''
                Default for :cylc:conf:`suite.rc[cylc]UTC mode`.
        ''')
        Conf('task event mail interval', VDR.V_INTERVAL, DurationFloat(300),
             desc='''
                Default for
                :cylc:conf:`suite.rc[cylc]task event mail interval`.
        ''')

        with Conf('events', desc='''
            You can define site defaults for each of the following options,
            details of which can be found under
            :cylc:conf:`suite.rc[cylc][events]`.
        '''):
            Conf('handlers', VDR.V_STRING_LIST)
            Conf('handler events', VDR.V_STRING_LIST)
            Conf('mail events', VDR.V_STRING_LIST)
            Conf('mail from', VDR.V_STRING)
            Conf('mail smtp', VDR.V_STRING)
            Conf('mail to', VDR.V_STRING)
            Conf('mail footer', VDR.V_STRING)
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
                Conf('foo', VDR.V_STRING, default='X')

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

    # suite
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

    # general
    with Conf('documentation', desc='''
        Documentation locations for the ``cylc doc`` command.
    '''):
        Conf('local', VDR.V_STRING, '', desc='''
            Path where the cylc documentation will appear if built locally.
        ''')
        Conf('online', VDR.V_STRING,
             'http://cylc.github.io/doc/built-sphinx/index.html', desc='''
            URL of the online cylc documentation.
        ''')
        Conf('cylc homepage', VDR.V_STRING, 'http://cylc.github.io/', desc='''
            URL of the cylc internet homepage, with links to documentation for
            the latest official release.
        ''')

    # general
    with Conf('document viewers', desc='''
        PDF and HTML viewers can be launched by cylc to view the
        documentation.
    '''):
        Conf('html', VDR.V_STRING, 'firefox', desc='''
            Your preferred web browser.
        ''')

    # client
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

    # platforms
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
            Conf('scp command',
                 VDR.V_STRING, 'scp -oBatchMode=yes -oConnectTimeout=10',
                 desc='''
                A string for the command used to copy files to a remote host.
                This is not used on the suite host unless you run local tasks
                under another user account. The value is assumed to be ``scp``
                with some initial options or a command that implements a
                similar interface to ``scp``.
            ''')
            Conf('ssh command',
                 VDR.V_STRING, 'ssh -oBatchMode=yes -oConnectTimeout=10',
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
                :cylc:conf:`suite.rc[runtime][<namespace>][remote]retrieve job
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
                :cylc:conf:`suite.rc[runtime][<namespace>][remote]retrieve job
                logs max size`.
                the specified host.
            ''')
            Conf('retrieve job logs retry delays', VDR.V_INTERVAL_LIST,
                 desc='''
                Global default for the
                :cylc:conf:`suite.rc[runtime][<namespace>][remote]retrieve job
                logs retry delays`.
                setting for the specified host.
            ''')
            Conf('task event handler retry delays', VDR.V_INTERVAL_LIST,
                 desc='''
                Host specific default for
                :cylc:conf:`suite.rc[runtime][<namespace>][events]handler retry
                delays`.
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
        with Conf('localhost', meta=Platform):
            Conf('hosts', VDR.V_STRING_LIST, ['localhost'])

    # Platform Groups
    with Conf('platform groups'):
        with Conf('<group>'):
            Conf('platforms', VDR.V_STRING_LIST)

    # task
    with Conf('task events', desc='''
        Global site/user defaults for
        :cylc:conf:`suite.rc[runtime][<namespace>][events]`.
    '''):
        Conf('execution timeout', VDR.V_INTERVAL)
        Conf('handlers', VDR.V_STRING_LIST)
        Conf('handler events', VDR.V_STRING_LIST)
        Conf('handler retry delays', VDR.V_INTERVAL_LIST, None)
        Conf('mail events', VDR.V_STRING_LIST)
        Conf('mail from', VDR.V_STRING)
        Conf('mail retry delays', VDR.V_INTERVAL_LIST)
        Conf('mail smtp', VDR.V_STRING)
        Conf('mail to', VDR.V_STRING)
        Conf('submission timeout', VDR.V_INTERVAL)

    # client
    with Conf('test battery', desc='''
        Settings for the automated development tests.

        .. note::
           The test battery reads ``flow-tests.rc`` instead of the normal
           site/user global config files (from the same locations, however).
    '''):
        Conf('remote platform with shared fs', VDR.V_STRING, desc='''
            The name of a remote platform that sees the same HOME file system
            as the host running the test battery.
        ''')
        Conf('remote platform', VDR.V_STRING, desc='''
            Platform name of a remote account that does not see the same home
            directory as the account running the test battery.
        ''')

        with Conf('batch systems', desc='''
            Settings for testing supported batch systems (job submission
            methods). The tests for a batch system are only performed if the
            batch system is available on the test host or a remote host
            accessible via SSH from the test host.
        '''):

            with Conf('<batch system name>', desc='''
                SYSTEM is the name of a supported batch system with automated
                tests.  This can currently be "loadleveler", "lsf", "pbs",
                "sge" and/or "slurm".
            '''):
                Conf('host', VDR.V_STRING, desc='''
                    The name of a host where commands for this batch system is
                    available. Use "localhost" if the batch system is available
                    on the host running the test battery. Any specified remote
                    host should be accessible via SSH from the host running the
                    test battery.
                ''')
                Conf('out viewer', VDR.V_STRING, desc='''
                    The command template (with ``%(job_id)s`` substitution)
                    for testing the run time stdout viewer functionality for
                    this batch system.
                ''')
                Conf('err viewer', VDR.V_STRING, desc='''
                    The command template (with ``%(job_id)s`` substitution)
                    for testing the run time stderr viewer functionality for
                    this batch system.
                ''')

                with Conf('directives', desc='''
                    The minimum set of directives that must be supplied to the
                    batch system on the site to initiate jobs for the tests.
                '''):
                    Conf('<directive>', VDR.V_STRING)

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
    with Conf('authentication', desc='''
        Authentication of client programs with suite server programs can be
        configured here, and overridden in suites if necessary with
        :cylc:conf:`suite.rc[cylc][authentication]`.

        The suite-specific passphrase must be installed on a user's account to
        authorize full control privileges (see
        :ref:`ConnectionAuthentication`). In the future we plan to move to a
        more traditional user account model so that each authorized user can
        have their own password.
    '''):
        # Allow owners to grant public shutdown rights at the most, not full
        # control.
        Conf(
            'public',
            VDR.V_STRING,
            default=Priv.STATE_TOTALS.name.lower().replace('_', '-'),
            options=[
                level.name.lower().replace('_', '-')
                for level in [
                    Priv.IDENTITY, Priv.DESCRIPTION,
                    Priv.STATE_TOTALS, Priv.READ, Priv.SHUTDOWN
                ]
            ],
            desc='''
                This sets the client privilege level for public access - i.e.
                no suite passphrase required.
            '''
        )

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

    u.obsolete('6.4.1', ['test battery', 'directives'])
    u.obsolete('6.11.0', ['state dump rolling archive length'])
    # Roll over is always done.
    u.obsolete('7.8.0', ['suite logging', 'roll over at start-up'])
    u.obsolete('7.8.1', ['documentation', 'local index'])
    u.obsolete('7.8.1', ['documentation', 'files', 'pdf user guide'])
    u.obsolete('7.8.1', ['documentation', 'files',
                         'single-page html user guide'])
    u.deprecate('7.8.1',
                ['documentation', 'files', 'multi-page html user guide'],
                ['documentation', 'local'])
    u.deprecate('8.0.0',
                ['documentation', 'files', 'html index'],
                ['documentation', 'local'])
    u.deprecate('8.0.0',
                ['documentation', 'urls', 'internet homepage'],
                ['documentation', 'cylc homepage'])
    u.obsolete('8.0.0', ['suite servers', 'scan hosts'])
    u.obsolete('8.0.0', ['suite servers', 'scan ports'])
    u.obsolete('8.0.0', ['communication'])
    u.obsolete('8.0.0', ['temporary directory'])
    u.obsolete('8.0.0', ['task host select command timeout'])
    u.obsolete('8.0.0', ['xtrigger function timeout'])
    u.obsolete('8.0.0', ['enable run directory housekeeping'])
    u.obsolete('8.0.0', ['task messaging'])

    u.upgrade()


class GlobalConfig(ParsecConfig):
    """
    Handle global (all suites) site and user configuration for cylc.
    User file values override site file values.
    """

    _DEFAULT = None
    _HOME = os.getenv('HOME') or get_user_home()
    CONF_BASENAME = "flow.rc"
    SITE_CONF_DIR = os.path.join(os.sep, 'etc', 'cylc', 'flow', CYLC_VERSION)
    USER_CONF_DIR = os.path.join(_HOME, '.cylc', 'flow', CYLC_VERSION)

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
            for conf_dir, conf_type in [
                    (self.SITE_CONF_DIR, upgrader.SITE_CONFIG),
                    (self.USER_CONF_DIR, upgrader.USER_CONFIG)]:
                fname = os.path.join(conf_dir, self.CONF_BASENAME)
                if not os.access(fname, os.F_OK | os.R_OK):
                    continue
                try:
                    self.loadcfg(fname, conf_type)
                except ParsecError as exc:
                    if conf_type == upgrader.SITE_CONFIG:
                        # Warn on bad site file (users can't fix it).
                        LOG.warning(
                            'ignoring bad %s %s:\n%s', conf_type, fname, exc)
                    else:
                        # Abort on bad user file (users can fix it).
                        LOG.error('bad %s %s', conf_type, fname)
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
