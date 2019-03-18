#!/usr/bin/env python3

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
"""Common options for all cylc commands."""

import logging
from optparse import OptionParser, OptionConflictError
import os
import sys

from cylc import LOG
import cylc.flags
from cylc.loggingutil import CylcLogFormatter


class CylcOptionParser(OptionParser):

    """Common options for all cylc CLI commands."""

    MULTITASK_USAGE = """
TASK_GLOB is a pattern to match task proxies or task families,
or groups of them:
* [CYCLE-POINT-GLOB/]TASK-NAME-GLOB[:TASK-STATE]
* [CYCLE-POINT-GLOB/]FAMILY-NAME-GLOB[:TASK-STATE]
* TASK-NAME-GLOB[.CYCLE-POINT-GLOB][:TASK-STATE]
* FAMILY-NAME-GLOB[.CYCLE-POINT-GLOB][:TASK-STATE]

For example, to match:
* all tasks in a cycle: '20200202T0000Z/*' or '*.20200202T0000Z'
* all tasks in the submitted status: ':submitted'
* retrying 'foo*' tasks in 0000Z cycles: 'foo*.*0000Z:retrying' or
  '*0000Z/foo*:retrying'
* retrying tasks in 'BAR' family: '*/BAR:retrying' or 'BAR.*:retrying'
* retrying tasks in 'BAR' or 'BAZ' families: '*/BA[RZ]:retrying' or
  'BA[RZ].*:retrying'"""

    def __init__(self, usage, argdoc=None, comms=False, noforce=False,
                 jset=False, multitask=False, prep=False, auto_add=True,
                 icp=False):

        self.auto_add = auto_add
        if argdoc is None:
            if prep:
                argdoc = [('SUITE', 'Suite name or path')]
            else:
                argdoc = [('REG', 'Suite name')]

        # noforce=True is for commands that don't use interactive prompts at
        # all

        if multitask:
            usage += self.MULTITASK_USAGE
        args = ""
        self.n_compulsory_args = 0
        self.n_optional_args = 0
        self.unlimited_args = False
        self.comms = comms
        self.jset = jset
        self.noforce = noforce
        self.prep = prep
        self.icp = icp
        self.suite_info = []

        maxlen = 0
        for arg in argdoc:
            if len(arg[0]) > maxlen:
                maxlen = len(arg[0])

        if argdoc:
            usage += "\n\nArguments:"
            for arg in argdoc:
                if arg[0].startswith('['):
                    self.n_optional_args += 1
                else:
                    self.n_compulsory_args += 1
                if arg[0].endswith('...]'):
                    self.unlimited_args = True

                args += arg[0] + " "

                pad = (maxlen - len(arg[0])) * ' ' + '               '
                usage += "\n   " + arg[0] + pad + arg[1]
            usage = usage.replace('ARGS', args)

        OptionParser.__init__(self, usage)

    def add_std_option(self, *args, **kwargs):
        """Add a standard option, ignoring override."""
        try:
            self.add_option(*args, **kwargs)
        except OptionConflictError:
            pass

    def add_std_options(self):
        """Add standard options if they have not been overridden."""
        self.add_std_option(
            "--user",
            help=(
                "Other user account name. This results in "
                "command reinvocation on the remote account."
            ),
            metavar="USER", action="store", dest="owner")
        self.add_std_option(
            "--host",
            help="Other host name. This results in "
            "command reinvocation on the remote account.",
            metavar="HOST", action="store", dest="host")
        self.add_std_option(
            "-v", "--verbose",
            help="Verbose output mode.",
            action="store_true", dest="verbose",
            default=(os.getenv("CYLC_VERBOSE", "false").lower() == "true"))
        self.add_std_option(
            "--debug",
            help="Output developer information and show exception tracebacks.",
            action="store_true", dest="debug",
            default=(os.getenv("CYLC_DEBUG", "false").lower() == "true"))

        if self.prep:
            self.add_std_option(
                "--suite-owner",
                help="Specify suite owner",
                metavar="OWNER", action="store", default=None,
                dest="suite_owner")

        if self.comms:
            self.add_std_option(
                "--port",
                help=(
                    "Suite port number on the suite host. "
                    "NOTE: this is retrieved automatically if "
                    "non-interactive ssh is configured to the suite host."
                ),
                metavar="INT", action="store", default=None, dest="port")
            self.add_std_option(
                "--use-ssh",
                help="Use ssh to re-invoke the command on the suite host.",
                action="store_true", default=False, dest="use_ssh")
            self.add_std_option(
                "--ssh-cylc",
                help="Location of cylc executable on remote ssh commands.",
                action="store", default="cylc", dest="ssh_cylc")
            self.add_std_option(
                "--no-login",
                help=(
                    "Do not use a login shell to run remote ssh commands. "
                    "The default is to use a login shell."
                ),
                action="store_false", default=True, dest="ssh_login")
            self.add_std_option(
                "--comms-timeout", "--pyro-timeout", metavar='SEC',
                help=(
                    "Set a timeout for network connections "
                    "to the running suite. The default is no timeout. "
                    "For task messaging connections see "
                    "site/user config file documentation."
                ),
                action="store", default=None, dest="comms_timeout")

            if not self.noforce:
                self.add_std_option(
                    "-f", "--force",
                    help=(
                        "Do not ask for confirmation before acting. "
                        "Note that it is not necessary to use this option "
                        "if interactive command prompts have been "
                        "disabled in the site/user config files."
                    ),
                    action="store_true", default=False, dest="force")

        if self.jset:
            self.add_std_option(
                "-s", "--set", metavar="NAME=VALUE",
                help=(
                    "Set the value of a Jinja2 template variable in the "
                    "suite definition. This option can be used multiple "
                    "times on the command line. "
                    "NOTE: these settings persist across suite restarts, "
                    "but can be set again on the \"cylc restart\" "
                    "command line if they need to be overridden."
                ),
                action="append", default=[], dest="templatevars")

            self.add_std_option(
                "--set-file", metavar="FILE",
                help=(
                    "Set the value of Jinja2 template variables in the "
                    "suite definition from a file containing NAME=VALUE "
                    "pairs (one per line). "
                    "NOTE: these settings persist across suite restarts, "
                    "but can be set again on the \"cylc restart\" "
                    "command line if they need to be overridden."
                ),
                action="store", default=None, dest="templatevars_file")

        if self.icp:
            self.add_option(
                "--icp",
                metavar="CYCLE_POINT",
                help=(
                    "Set initial cycle point. "
                    "Required if not defined in suite.rc."))

    def parse_args(self, remove_opts=None):
        """Parse options and arguments, overrides OptionParser.parse_args."""
        if self.auto_add:
            # Add common options after command-specific options.
            self.add_std_options()

        if remove_opts:
            for opt in remove_opts:
                try:
                    self.remove_option(opt)
                except ValueError:
                    pass

        (options, args) = OptionParser.parse_args(self)

        if len(args) < self.n_compulsory_args:
            self.error("Wrong number of arguments (too few)")

        elif not self.unlimited_args and \
                len(args) > self.n_compulsory_args + self.n_optional_args:
            self.error("Wrong number of arguments (too many)")

        if self.jset:
            if options.templatevars_file:
                options.templatevars_file = os.path.abspath(os.path.expanduser(
                    options.templatevars_file))

        cylc.flags.verbose = options.verbose
        cylc.flags.debug = options.debug

        # Set up stream logging for CLI. Note:
        # 1. On choosing STDERR: Log messages are diagnostics, so STDERR is the
        #    better choice for the logging stream. This allows us to use STDOUT
        #    for verbosity agnostic outputs.
        # 2. Suite server programs will remove this handler when it becomes a
        #    daemon.
        if options.debug or options.verbose:
            LOG.setLevel(logging.DEBUG)
        else:
            LOG.setLevel(logging.INFO)
        # Remove NullHandler before add the StreamHandler
        while LOG.handlers:
            LOG.handlers[0].close()
            LOG.removeHandler(LOG.handlers[0])
        errhandler = logging.StreamHandler(sys.stderr)
        errhandler.setFormatter(CylcLogFormatter())
        LOG.addHandler(errhandler)

        return (options, args)
