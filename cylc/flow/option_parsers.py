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
"""Common options for all cylc commands."""

from contextlib import suppress
import logging
from optparse import (
    OptionParser,
    OptionConflictError,
    Values,
    Option,
    IndentedHelpFormatter
)
import os
import re
from ansimarkup import (
    parse as cparse,
    strip as cstrip
)

import sys
from textwrap import dedent
from typing import Any, Dict, Optional, List, Tuple

from cylc.flow import LOG
from cylc.flow.exceptions import WorkflowConfigError
from cylc.flow.pathutil import is_in_a_rundir
from cylc.flow.terminal import supports_color, DIM
import cylc.flow.flags
from cylc.flow.loggingutil import (
    CylcLogFormatter,
    setup_segregated_log_streams,
)

WORKFLOW_ID_ARG_DOC = ('WORKFLOW', 'Workflow ID')
WORKFLOW_ID_MULTI_ARG_DOC = ('WORKFLOW ...', 'Workflow ID(s)')
WORKFLOW_ID_OR_PATH_ARG_DOC = ('WORKFLOW | PATH', 'Workflow ID or path')
ID_MULTI_ARG_DOC = ('ID ...', 'Workflow/Cycle/Family/Task ID(s)')
FULL_ID_MULTI_ARG_DOC = ('ID ...', 'Cycle/Family/Task ID(s)')

SHORTLINK_TO_ICP_DOCS = "https://bit.ly/3MYHqVh"

icp_option = Option(
    "--initial-cycle-point", "--icp",
    metavar="CYCLE_POINT or OFFSET",
    help=(
        "Set the initial cycle point. "
        "Required if not defined in flow.cylc."
        "\nMay be either an absolute point or an offset: See "
        f"{SHORTLINK_TO_ICP_DOCS} (Cylc documentation link)."
    ),
    action="store",
    dest="icp",
)


def format_shell_examples(string):
    """Put comments in the terminal "diminished" colour."""
    return cparse(
        re.sub(
            r'^(\s*(?:\$[^#]+)?)(#.*)$',
            rf'\1<{DIM}>\2</{DIM}>',
            string,
            flags=re.M,
        )
    )


def format_help_headings(string):
    """Put "headings" in bold.

    Where "headings" are lines with no indentation which are followed by a
    colon e.g:

    Examples:
      ...

    """
    return cparse(
        re.sub(
            r'^(\w.*:)$',
            r'<bold>\1</bold>',
            string,
            flags=re.M,
        )
    )


def verbosity_to_log_level(verb: int) -> int:
    """Convert Cylc verbosity to log severity level."""
    if verb < 0:
        return logging.WARNING
    if verb > 0:
        return logging.DEBUG
    return logging.INFO


def log_level_to_verbosity(lvl: int) -> int:
    """Convert log severity level to Cylc verbosity.

    Examples:
        >>> log_level_to_verbosity(logging.NOTSET)
        2
        >>> log_level_to_verbosity(logging.DEBUG)
        1
        >>> log_level_to_verbosity(logging.INFO)
        0
        >>> log_level_to_verbosity(logging.WARNING)
        -1
        >>> log_level_to_verbosity(logging.ERROR)
        -1
    """
    if lvl < logging.DEBUG:
        return 2
    if lvl < logging.INFO:
        return 1
    if lvl == logging.INFO:
        return 0
    return -1


def verbosity_to_opts(verb: int) -> List[str]:
    """Convert Cylc verbosity to the CLI opts required to replicate it.

    Examples:
        >>> verbosity_to_opts(0)
        []
        >>> verbosity_to_opts(-2)
        ['-q', '-q']
        >>> verbosity_to_opts(2)
        ['-v', '-v']

    """
    return [
        '-q'
        for _ in range(verb, 0)
    ] + [
        '-v'
        for _ in range(0, verb)
    ]


def verbosity_to_env(verb: int) -> Dict[str, str]:
    """Convert Cylc verbosity to the env vars required to replicate it.

    Examples:
        >>> verbosity_to_env(0)
        {'CYLC_VERBOSE': 'false', 'CYLC_DEBUG': 'false'}
        >>> verbosity_to_env(1)
        {'CYLC_VERBOSE': 'true', 'CYLC_DEBUG': 'false'}
        >>> verbosity_to_env(2)
        {'CYLC_VERBOSE': 'true', 'CYLC_DEBUG': 'true'}

    """
    return {
        'CYLC_VERBOSE': str((verb > 0)).lower(),
        'CYLC_DEBUG': str((verb > 1)).lower(),
    }


def env_to_verbosity(env: dict) -> int:
    """Extract verbosity from environment variables.

    Examples:
        >>> env_to_verbosity({})
        0
        >>> env_to_verbosity({'CYLC_VERBOSE': 'true'})
        1
        >>> env_to_verbosity({'CYLC_DEBUG': 'true'})
        2
        >>> env_to_verbosity({'CYLC_DEBUG': 'TRUE'})
        2

    """
    return (
        2 if env.get('CYLC_DEBUG', '').lower() == 'true'
        else 1 if env.get('CYLC_VERBOSE', '').lower() == 'true'
        else 0
    )


class CylcOption(Option):
    """Optparse option which adds a decrement action."""

    ACTIONS = Option.ACTIONS + ('decrement',)
    STORE_ACTIONS = Option.STORE_ACTIONS + ('decrement',)

    def take_action(self, action, dest, opt, value, values, parser):
        if action == 'decrement':
            setattr(values, dest, values.ensure_value(dest, 0) - 1)
        else:
            Option.take_action(self, action, dest, opt, value, values, parser)


class CylcHelpFormatter(IndentedHelpFormatter):
    def _format(self, text):
        """Format help (usage) text on the fly to handle coloring.

        Help is printed to the terminal before color initialization for general
        command output.

        If coloring is wanted:
          - Add color tags to shell examples
        Else:
          - Strip any hardwired color tags

        """
        if (
            hasattr(self.parser.values, 'color')
            and (
                self.parser.values.color == "always"
                or (
                    self.parser.values.color == "auto"
                    and supports_color()
                )
            )
        ):
            # Add color formatting to examples text.
            text = format_shell_examples(
                format_help_headings(text)
            )
        else:
            # Strip any hardwired formatting
            text = cstrip(text)
        return text

    def format_usage(self, usage):
        return super().format_usage(self._format(usage))

    # If we start using "description" as well as "usage" (also epilog):
    # def format_description(self, description):
    #     return super().format_description(self._format(description))


class CylcOptionParser(OptionParser):

    """Common options for all cylc CLI commands."""

    MULTITASK_USAGE = cparse(dedent('''
        This command can operate on multiple tasks, globs and selectors may
        be used:
            Multiple Tasks:
                <dim># Operate on two tasks</dim>
                workflow //cycle-1/task-1 //cycle-2/task-2

            Globs (note: globs should be quoted and only match active tasks):
                <dim># Match any the active task "foo" in all cycles</dim>
                '//*/foo'

                <dim># Match the tasks "foo-1" and "foo-2"</dim>
                '//*/foo-[12]'

            Selectors (note: selectors only match active tasks):
                <dim># match all failed tasks in cycle "1"</dim>
                //1:failed

            See `cylc help id` for more details.
    '''))
    MULTIWORKFLOW_USAGE = cparse(dedent('''
        This command can operate on multiple workflows, globs may also be used:
            Multiple Workflows:
                <dim># Operate on two workflows</dim>
                workflow-1 workflow-2

            Globs (note: globs should be quoted):
                <dim># Match all workflows</dim>
                '*'

                <dim># Match the workflows foo-1, foo-2</dim>
                'foo-[12]'

            See `cylc help id` for more details.
    '''))

    def __init__(
        self,
        usage: str,
        argdoc: Optional[List[Tuple[str, str]]] = None,
        comms: bool = False,
        jset: bool = False,
        revalidate: bool = False,
        multitask: bool = False,
        multiworkflow: bool = False,
        auto_add: bool = True,
        color: bool = True,
        segregated_log: bool = False
    ) -> None:
        """
        Args:
            usage: Usage instructions. Typically this will be the __doc__ of
                the script module.
            argdoc: The args for the command, to be inserted into the usage
                instructions. Optional list of tuples of (name, description).
            comms: If True, allow the --comms-timeout option.
            jset: If True, allow the Jinja2 --set option.
            revalidate: If True, allow the --revalidate option.
            multitask: If True, insert the multitask text into the
                usage instructions.
            multiworkflow: If True, insert the multiworkflow text into the
                usage instructions.
            auto_add: If True, allow the standard options.
            color: If True, allow the --color option.
            segregated_log: If False, write all logging entries to stderr.
                If True, write entries at level < WARNING to stdout and
                entries at level >= WARNING to stderr.
        """
        self.auto_add = auto_add

        if multiworkflow:
            usage += self.MULTIWORKFLOW_USAGE

        if multitask:
            usage += self.MULTITASK_USAGE

        args = ""
        self.n_compulsory_args = 0
        self.n_optional_args = 0
        self.unlimited_args = False
        self.comms = comms
        self.jset = jset
        self.revalidate = revalidate
        self.color = color
        # Whether to log messages that are below warning level to stdout
        # instead of stderr:
        self.segregated_log = segregated_log

        if argdoc:
            maxlen = max(len(arg) for arg, _ in argdoc)
            usage += "\n\nArguments:"
            for arg, descr in argdoc:
                if arg.startswith('['):
                    self.n_optional_args += 1
                else:
                    self.n_compulsory_args += 1
                if arg.rstrip(']').endswith('...'):
                    self.unlimited_args = True

                args += arg + " "

                pad = (maxlen - len(arg)) * ' ' + '               '
                usage += "\n   " + arg + pad + descr
            usage = usage.replace('ARGS', args)

        OptionParser.__init__(
            self,
            usage,
            option_class=CylcOption,
            formatter=CylcHelpFormatter()
        )

    def add_std_option(self, *args, **kwargs):
        """Add a standard option, ignoring override."""
        with suppress(OptionConflictError):
            self.add_option(*args, **kwargs)

    def add_std_options(self):
        """Add standard options if they have not been overridden."""
        self.add_std_option(
            "-q", "--quiet",
            help="Decrease verbosity.",
            action='decrement',
            dest='verbosity',
        )
        self.add_std_option(
            "-v", "--verbose",
            help="Increase verbosity.",
            dest='verbosity',
            action='count',
            default=env_to_verbosity(os.environ)
        )
        self.add_std_option(
            "--debug",
            help="Equivalent to -v -v",
            dest="verbosity",
            action='store_const',
            const=2
        )
        self.add_std_option(
            "--no-timestamp",
            help="Don't timestamp logged messages.",
            action="store_false", dest="log_timestamp", default=True)

        if self.color:
            self.add_std_option(
                '--color', '--colour', metavar='WHEN', action='store',
                default='auto', choices=['never', 'auto', 'always'],
                help=(
                    "When to use color/bold text in terminal output."
                    " Options are 'never', 'auto' and 'always'."
                )
            )

        if self.comms:
            self.add_std_option(
                "--comms-timeout", metavar='SEC',
                help=(
                    "Set a timeout for network connections "
                    "to the running workflow. The default is no timeout. "
                    "For task messaging connections see "
                    "site/user config file documentation."
                ),
                action="store", default=None, dest="comms_timeout")

        if self.jset:
            self.add_std_option(
                "-s", "--set", metavar="NAME=VALUE",
                help=(
                    "Set the value of a Jinja2 template variable in the"
                    " workflow definition."
                    " Values should be valid Python literals so strings"
                    " must be quoted"
                    " e.g. 'STR=\"string\"', INT=43, BOOL=True."
                    " This option can be used multiple "
                    " times on the command line."
                    " NOTE: these settings persist across workflow restarts,"
                    " but can be set again on the \"cylc play\""
                    " command line if they need to be overridden."
                ),
                action="append", default=[], dest="templatevars")

            self.add_std_option(
                "--set-file", metavar="FILE",
                help=(
                    "Set the value of Jinja2 template variables in the "
                    "workflow definition from a file containing NAME=VALUE "
                    "pairs (one per line). "
                    "As with --set values should be valid Python literals "
                    "so strings must be quoted e.g. STR='string'. "
                    "NOTE: these settings persist across workflow restarts, "
                    "but can be set again on the \"cylc play\" "
                    "command line if they need to be overridden."
                ),
                action="store", default=None, dest="templatevars_file")

        if self.revalidate:
            self.add_std_option(
                '--revalidate',
                help="Get template variables from prevous workflow run.",
                action='store_true', default=False
            )

    def add_cylc_rose_options(self) -> None:
        """Add extra options for cylc-rose plugin if it is installed."""
        try:
            __import__('cylc.rose')
        except ImportError:
            return
        self.add_option(
            "--opt-conf-key", "-O",
            help=(
                "Use optional Rose Config Setting "
                "(If Cylc-Rose is installed)"
            ),
            action="append",
            default=[],
            dest="opt_conf_keys"
        )
        self.add_option(
            "--define", '-D',
            help=(
                "Each of these overrides the `[SECTION]KEY` setting in a "
                "`rose-suite.conf` file. "
                "Can be used to disable a setting using the syntax "
                "`--define=[SECTION]!KEY` or even `--define=[!SECTION]`."
            ),
            action="append",
            default=[],
            dest="defines"
        )
        self.add_option(
            "--rose-template-variable", '-S', '--define-suite',
            help=(
                "As `--define`, but with an implicit `[SECTION]` for "
                "workflow variables."
            ),
            action="append",
            default=[],
            dest="rose_template_vars"
        )

    def parse_args(self, api_args, remove_opts=None):
        """Parse options and arguments, overrides OptionParser.parse_args.

        Args:
            api_args (list):
                Command line options if passed via Python as opposed to
                sys.argv
            remove_opts (list):
                List of standard options to remove before parsing.

        """
        if self.auto_add:
            # Add common options after command-specific options.
            self.add_std_options()

        if remove_opts:
            for opt in remove_opts:
                with suppress(ValueError):
                    self.remove_option(opt)

        (options, args) = OptionParser.parse_args(self, api_args)

        if len(args) < self.n_compulsory_args:
            self.error("Wrong number of arguments (too few)")

        elif (
            not self.unlimited_args
            and len(args) > self.n_compulsory_args + self.n_optional_args
        ):
            self.error("Wrong number of arguments (too many)")

        if self.jset and options.templatevars_file:
            options.templatevars_file = os.path.abspath(os.path.expanduser(
                options.templatevars_file)
            )

        cylc.flow.flags.verbosity = options.verbosity

        # Set up stream logging for CLI. Note:
        # 1. On choosing STDERR: Log messages are diagnostics, so STDERR is the
        #    better choice for the logging stream. This allows us to use STDOUT
        #    for verbosity agnostic outputs.
        # 2. Scheduler will remove this handler when it becomes a daemon.
        LOG.setLevel(verbosity_to_log_level(options.verbosity))
        # Remove NullHandler before add the StreamHandler

        while LOG.handlers:
            LOG.handlers[0].close()
            LOG.removeHandler(LOG.handlers[0])
        log_handler = logging.StreamHandler(sys.stderr)
        log_handler.setFormatter(CylcLogFormatter(
            timestamp=options.log_timestamp,
            dev_info=(options.verbosity > 2)
        ))
        LOG.addHandler(log_handler)

        if self.segregated_log:
            setup_segregated_log_streams(LOG, log_handler)

        return (options, args)

    @staticmethod
    def optional(arg: Tuple[str, str]) -> Tuple[str, str]:
        """Make an argdoc tuple display as an optional arg with
        square brackets."""
        name, doc = arg
        return (f'[{name}]', doc)


class Options:
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
        >>> PythonOptions(e=6)
        Traceback (most recent call last):
        ValueError: e

        You can reuse the object multiple times
        >>> opts2 = PythonOptions(a=2)
        >>> id(opts) == id(opts2)
        False

    """

    def __init__(
        self, parser: OptionParser, overrides: Optional[Dict[str, Any]] = None
    ) -> None:
        if overrides is None:
            overrides = {}
        if isinstance(parser, CylcOptionParser) and parser.auto_add:
            parser.add_std_options()
        self.defaults = {**parser.defaults, **overrides}

    def __call__(self, **kwargs) -> Values:
        opts = Values(self.defaults)
        for key, value in kwargs.items():
            if not hasattr(opts, key):
                raise ValueError(key)
            setattr(opts, key, value)

        return opts


def can_revalidate(flow_file, opts):
    if not is_in_a_rundir(flow_file) and opts.revalidate:
        raise WorkflowConfigError(
            'Revalidation only works with installed workflows.'
        )
    return True
