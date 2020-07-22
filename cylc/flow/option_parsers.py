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
"""Common options for all cylc commands."""

import logging
from optparse import OptionParser, OptionConflictError, Values
import os
import re
import sys

from ansimarkup import parse as cparse

from cylc.flow import LOG
import cylc.flow.flags
from cylc.flow.loggingutil import CylcLogFormatter


class CylcOptionParser(OptionParser):

    """Common options for all cylc CLI commands."""

    # Shared text for commands which can, & cannot, glob on cycle points:
    MULTI_USAGE_TEMPLATE = """{0}

For example, to match:{1}"""
    # Help text either including or excluding globbing on cycle points:
    WITH_CYCLE_GLOBS = """
One or more TASK_GLOBs can be given to match task instances in the current task
pool, by task or family name pattern, cycle point pattern, and task state. Note
this command does not operate on tasks at any arbitrary point in the abstract
workflow graph - tasks not already in the pool must be inserted first with the
"cylc insert" command in order to be matched.
* [CYCLE-POINT-GLOB/]TASK-NAME-GLOB[:TASK-STATE]
* [CYCLE-POINT-GLOB/]FAMILY-NAME-GLOB[:TASK-STATE]
* TASK-NAME-GLOB[.CYCLE-POINT-GLOB][:TASK-STATE]
* FAMILY-NAME-GLOB[.CYCLE-POINT-GLOB][:TASK-STATE]"""
    WITHOUT_CYCLE_GLOBS = """
TASK_GLOB matches task or family names, to insert task instances into the pool
at a specific given cycle point. (NOTE this differs from other commands which
match name and cycle point patterns against instances already in the pool).
* CYCLE-POINT/TASK-NAME-GLOB
* CYCLE-POINT/FAMILY-NAME-GLOB
* TASK-NAME-GLOB.CYCLE-POINT
* FAMILY-NAME-GLOB.CYCLE-POINT"""
    WITH_CYCLE_EXAMPLES = """
* all tasks in a cycle: '20200202T0000Z/*' or '*.20200202T0000Z'
* all tasks in the submitted status: ':submitted'
* retrying 'foo*' tasks in 0000Z cycles: 'foo*.*0000Z:retrying' or
  '*0000Z/foo*:retrying'
* retrying tasks in 'BAR' family: '*/BAR:retrying' or 'BAR.*:retrying'
* retrying tasks in 'BAR' or 'BAZ' families: '*/BA[RZ]:retrying' or
  'BA[RZ].*:retrying'"""
    WITHOUT_CYCLE_EXAMPLES = """
* all tasks: '20200202T0000Z/*' or '*.20200202T0000Z'
* all tasks named model_N for some character N: '20200202T0000Z/model_?' or
  'model_?.20200202T0000Z'
* all tasks in 'BAR' family: '20200202T0000Z/BAR' or 'BAR.20200202T0000Z'
* all tasks in 'BAR' or 'BAZ' families: '20200202T0000Z/BA[RZ]' or
  'BA[RZ].20200202T0000Z'"""
    MULTITASKCYCLE_USAGE = MULTI_USAGE_TEMPLATE.format(
        WITH_CYCLE_GLOBS, WITH_CYCLE_EXAMPLES)
    MULTITASK_USAGE = MULTI_USAGE_TEMPLATE.format(
        WITHOUT_CYCLE_GLOBS, WITHOUT_CYCLE_EXAMPLES)

    def __init__(self, usage, argdoc=None, comms=False, noforce=False,
                 jset=False, multitask=False, multitask_nocycles=False,
                 prep=False, auto_add=True, icp=False, color=True):

        self.auto_add = auto_add
        if argdoc is None:
            if prep:
                argdoc = [('SUITE', 'Suite name or path')]
            else:
                argdoc = [('REG', 'Suite name')]

        # make comments grey in usage for readability
        usage = cparse(
            re.sub(
                r'^(\s*(?:\$[^#]+)?)(#.*)$',
                r'\1<dim>\2</dim>',
                usage,
                flags=re.M
            )
        )

        # noforce=True is for commands not using interactive prompts at all

        if multitask:
            usage += self.MULTITASKCYCLE_USAGE
        elif multitask_nocycles:  # glob on task names but not cycle points
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
        self.color = color

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
            "-v", "--verbose",
            help="Verbose output mode.",
            action="store_true", dest="verbose",
            default=(os.getenv("CYLC_VERBOSE", "false").lower() == "true"))
        self.add_std_option(
            "--debug",
            help="Output developer information and show exception tracebacks.",
            action="store_true", dest="debug",
            default=(os.getenv("CYLC_DEBUG", "false").lower() == "true"))

        if self.color:
            self.add_std_option(
                '--color', '--colour', metavar='WHEN', action='store',
                default='auto', choices=['never', 'auto', 'always'],
                help='Determine when to use color in terminal output.')

        if self.prep:
            self.add_std_option(
                "--suite-owner",
                help="Specify suite owner",
                metavar="OWNER", action="store", default=None,
                dest="suite_owner")

        if self.comms:
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
                "--initial-cycle-point", "--initial-point", "--icp", "--ict",
                metavar="CYCLE_POINT",
                help=(
                    "Set the initial cycle point. "
                    "Required if not defined in suite.rc."
                ),
                action="store",
                dest="icp",
            )

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

        cylc.flow.flags.verbose = options.verbose
        cylc.flow.flags.debug = options.debug

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


class Options(Values):
    """Wrapper to allow Python API access to optparse CLI functionality.

    Example:
        Create an optparse parser as normal:
        >>> import optparse
        >>> parser = optparse.OptionParser()
        >>> _ = parser.add_option('-a', default=1)
        >>> _ = parser.add_option('-b', default=2)

        Create an Options object from the parser:
        >>> PythonOptions = Options(parser, overrides={'c': 3})

        "Parse" options via Python API:
        >>> opts = PythonOptions(a=4)

        Access options as normal:
        >>> opts.a
        4
        >>> opts.b
        2
        >>> opts.c
        3

        Optparse allows you to create new options on the fly:
        >>> opts.d = 5
        >>> opts.d
        5

        But you can't create new options at initiation, this gives us basic
        input validation:
        >>> opts(e=6)
        Traceback (most recent call last):
        ValueError: e

    """

    def __init__(self, parser, overrides=None):
        if overrides is None:
            overrides = {}
        defaults = {**parser.defaults, **overrides}
        Values.__init__(self, defaults)

    def __call__(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                raise ValueError(key)
        return self
