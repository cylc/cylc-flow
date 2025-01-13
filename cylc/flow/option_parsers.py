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
from itertools import product
from optparse import (
    OptionParser,
    Values,
    Option,
    IndentedHelpFormatter,
)
import os
import re
import sys
from textwrap import dedent
from typing import Any, Dict, Iterable, Optional, List, Set, Tuple

from ansimarkup import (
    parse as cparse,
    strip as cstrip
)

from cylc.flow import LOG
from cylc.flow.terminal import should_use_color, DIM
import cylc.flow.flags
from cylc.flow.loggingutil import (
    CylcLogFormatter,
    setup_segregated_log_streams,
)
from cylc.flow.log_level import (
    env_to_verbosity,
    verbosity_to_log_level
)

WORKFLOW_ID_ARG_DOC = ('WORKFLOW', 'Workflow ID')
OPT_WORKFLOW_ID_ARG_DOC = ('[WORKFLOW]', 'Workflow ID')
WORKFLOW_ID_MULTI_ARG_DOC = ('WORKFLOW ...', 'Workflow ID(s)')
WORKFLOW_ID_OR_PATH_ARG_DOC = ('WORKFLOW | PATH', 'Workflow ID or path')
ID_SEL_ARG_DOC = ('ID[:sel]', 'WORKFLOW-ID[[//CYCLE[/TASK]]:selector]')
ID_MULTI_ARG_DOC = ('ID ...', 'Workflow/Cycle/Family/Task ID(s)')
FULL_ID_MULTI_ARG_DOC = ('ID ...', 'Cycle/Family/Task ID(s)')

SHORTLINK_TO_ICP_DOCS = "https://bit.ly/3MYHqVh"
DOUBLEDASH = '--'


class OptionSettings():
    """Container for info about a command line option

    Despite some similarities this is not to be confused with
    optparse.Option: This a container for information which may or may
    not be passed to optparse depending on the results of
    cylc.flow.option_parsers(thismodule).combine_options_pair.
    """

    def __init__(
        self,
        argslist: List[str],
        sources: Optional[Set[str]] = None,
        useif: str = '',
        **kwargs
    ):
        """Init function:

        Args:
            arglist: list of arguments for optparse.Option.
            sources: set of CLI scripts which use this option.
            useif: badge for use by Cylc optionparser.
            **kwargs: kwargs for optparse.option.
        """
        self.args: List[str] = argslist
        self.kwargs: Dict[str, Any] = kwargs
        self.sources: Set[str] = sources if sources is not None else set()
        self.useif: str = useif

    def __eq__(self, other):
        """Args and Kwargs, but not other props equal.

        (Also make an exception for kwargs['help'] to allow lists of sources
        prepended to 'help' to be passed through.)
        """
        return (
            (
                {k: v for k, v in self.kwargs.items() if k != 'help'}
                == {k: v for k, v in other.kwargs.items() if k != 'help'}
            )
            and self.args == other.args
        )

    def __and__(self, other):
        """Is there a set intersection between arguments."""
        return list(set(self.args).intersection(set(other.args)))

    def __sub__(self, other):
        """Set difference on args."""
        return list(set(self.args) - set(other.args))

    def _in_list(self, others):
        """CLI arguments for this option found in any of a list of
        other options."""
        return any(self & other for other in others)

    def _update_sources(self, other):
        """Update the sources from this and 1 other OptionSettings object"""
        self.sources = {*self.sources, *other.sources}


ICP_OPTION = OptionSettings(
    ["--initial-cycle-point", "--icp"],
    help=(
        "Set the initial cycle point."
        " Required if not defined in flow.cylc."
        "\nMay be either an absolute point or an offset: See"
        f" {SHORTLINK_TO_ICP_DOCS} (Cylc documentation link)."
    ),
    metavar="CYCLE_POINT or OFFSET",
    action='store',
    dest="icp"
)

AGAINST_SOURCE_OPTION = OptionSettings(
    ['--against-source'],
    help=(
        "Load the workflow configuration from the source directory it was"
        " installed from using any options (e.g. template variables) which"
        " have been set in the installation."
        " This is useful if you want to see how changes made to the workflow"
        " source would affect the installation if reinstalled."
        " Note if this option is used the provided workflow must have been"
        " installed by `cylc install`."
    ),
    dest='against_source',
    action='store_true',
    default=False
)


icp_option = Option(
    *ICP_OPTION.args, **ICP_OPTION.kwargs)  # type: ignore[arg-type]


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
    colon.
    """
    return cparse(
        re.sub(
            r'^(\w.*:)$',
            r'<bold>\1</bold>',
            string,
            flags=re.M,
        )
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
    """This formatter handles colour in help text, and automatically
    colourises headings & shell examples."""

    def _format(self, text: str) -> str:
        """Format help (usage) text on the fly to handle coloring.

        Help is printed to the terminal before color initialization for general
        command output.

        If coloring is wanted:
          - Add color tags to shell examples
        Else:
          - Strip any hardwired color tags

        """
        if should_use_color(self.parser.values):
            # Add color formatting to examples text.
            return format_shell_examples(
                format_help_headings(text)
            )
        # Else strip any hardwired formatting
        return cstrip(text)

    def format_usage(self, usage: str) -> str:
        return super().format_usage(self._format(usage))

    # If we start using "description" as well as "usage" (also epilog):
    # def format_description(self, description):
    #     return super().format_description(self._format(description))

    def format_option(self, option: Option) -> str:
        """Format help text for options."""
        if option.help:
            if should_use_color(self.parser.values):
                option.help = cparse(option.help)
            else:
                option.help = cstrip(option.help)
        return super().format_option(option)


class CylcOptionParser(OptionParser):

    """Common options for all cylc CLI commands."""

    MULTITASK_USAGE = dedent('''
        This command can operate on multiple tasks. Globs and selectors may
        be used to match active tasks:
            Multiple Tasks:
                # Operate on two tasks
                workflow //cycle-1/task-1 //cycle-2/task-2

            Globs (note: globs should be quoted and only match active tasks):
                # Match any active task "foo" in all cycles
                '//*/foo'

                # Match the tasks "foo-1" and "foo-2"
                '//*/foo-[12]'

            Selectors (note: selectors only match active tasks):
                # match all failed tasks in cycle "1"
                //1:failed

            See `cylc help id` for more details.
    ''')
    MULTIWORKFLOW_USAGE = dedent('''
        This command can operate on multiple workflows. Globs may be used:
            Multiple Workflows:
                # Operate on two workflows
                workflow-1 workflow-2

            Globs (note: globs should be quoted):
                # Match all workflows
                '*'

                # Match the workflows foo-1, foo-2
                'foo-[12]'

            See `cylc help id` for more details.
    ''')

    CAN_BE_USED_MULTIPLE = (
        " This option can be used multiple times on the command line.")

    NOTE_PERSIST_ACROSS_RESTARTS = (
        " NOTE: these settings persist across workflow restarts,"
        " but can be set again on the \"cylc play\""
        " command line if they need to be overridden."
    )

    STD_OPTIONS = [
        OptionSettings(
            ['-q', '--quiet'], help='Decrease verbosity.',
            action='decrement', dest='verbosity', useif='all'),
        OptionSettings(
            ['-v', '--verbose'], help='Increase Verbosity',
            dest='verbosity', action='count',
            default=env_to_verbosity(os.environ), useif='all'),
        OptionSettings(
            ['--debug'], help='Equivalent to -v -v',
            dest='verbosity', action='store_const', const=2, useif='all'),
        OptionSettings(
            ['--timestamp'],
            help='Add a timestamp to messages logged to the terminal.',
            action='store_true', dest='log_timestamp',
            default=False, useif='all'),
        OptionSettings(
            ['--no-timestamp'], help="Don't add a timestamp to messages logged"
            " to the terminal (this does nothing - it is now the default.",
            action='store_false', dest='_noop',
            default=False, useif='all'),
        OptionSettings(
            ['--color', '--colour'], metavar='WHEN', action='store',
            default='auto', choices=['never', 'auto', 'always'],
            help=(
                "When to use color/bold text in terminal output."
                " Options are 'never', 'auto' and 'always'."
            ),
            useif='color'),
        OptionSettings(
            ['--comms-timeout'], metavar='SEC',
            help=(
                "Set the timeout for communication with the running workflow."
                " The default is determined by the setup, 5 seconds for"
                " TCP comms and 300 for SSH."
                " If connections timeout, it likely means either, a complex"
                " request has been issued (e.g. cylc tui); there is a network"
                " issue; or a problem with the scheduler. Increasing the"
                " timeout will help with the first case."
            ),
            action='store', default=None, dest='comms_timeout', useif='comms'),
        OptionSettings(
            ['-s', '--set'], metavar='NAME=VALUE',
            help=(
                "Set the value of a Jinja2 template variable in the"
                " workflow definition."
                " Values should be valid Python literals so strings"
                " must be quoted"
                " e.g. 'STR=\"string\"', INT=43, BOOL=True."
                + CAN_BE_USED_MULTIPLE
                + NOTE_PERSIST_ACROSS_RESTARTS
            ),
            action='append', default=[], dest='templatevars', useif='jset'
        ),
        OptionSettings(
            ['-z', '--set-list', '--template-list'],
            metavar='NAME=VALUE1,VALUE2,...',
            # NOTE: deliberate non-breaking spaces in help text:
            help=(
                'A more convenient alternative to --set for defining a list'
                ' of strings. E.G.'
                ' "-z FOO=a,b,c" is shorthand for'
                ' "-s FOO=[\'a\',\'b\',\'c\']".'
                ' Commas can be present in values if quoted, e.g.'
                ' "-z FOO=a,\'b,c\'" is shorthand for'
                ' "-s FOO=[\'a\',\'b,c\']".'
                + CAN_BE_USED_MULTIPLE
                + NOTE_PERSIST_ACROSS_RESTARTS
            ),
            action='append', default=[], dest='templatevars_lists',
            useif='jset'
        ),
        OptionSettings(
            ['--set-file'], metavar='FILE',
            help=(
                "Set the value of Jinja2 template variables in the"
                " workflow definition from a file containing NAME=VALUE"
                " pairs (one per line)."
                " As with --set values should be valid Python literals "
                " so strings must be quoted e.g. STR='string'."
                + NOTE_PERSIST_ACROSS_RESTARTS
            ),
            action='store', default=None, dest='templatevars_file',
            useif='jset'
        )
    ]

    def __init__(
        self,
        usage: str,
        argdoc: Optional[List[Tuple[str, str]]] = None,
        comms: bool = False,
        jset: bool = False,
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

    def get_std_options(self):
        """Get a data-structure of standard options"""
        opts = []
        for opt in self.STD_OPTIONS:
            if (
                opt.useif == 'all'
                or hasattr(self, opt.useif) and getattr(self, opt.useif)
            ):
                opts.append(opt)
        return opts

    def add_std_options(self):
        """Add standard options if they have not been overridden."""
        for option in self.get_std_options():
            if not any(self.has_option(i) for i in option.args):
                self.add_option(*option.args, **option.kwargs)

    @staticmethod
    def get_cylc_rose_options():
        """Returns a list of option dictionaries if Cylc Rose exists."""
        try:
            __import__('cylc.rose')
        except ImportError:
            return []
        return [
            OptionSettings(
                ["--opt-conf-key", "-O"],
                help=(
                    "Use optional Rose Config Setting"
                    " (If Cylc-Rose is installed)"),
                action="append", default=[], dest="opt_conf_keys",
                sources={'cylc-rose'},
            ),
            OptionSettings(
                ["--define", '-D'],
                help=(
                    "Each of these overrides the `[SECTION]KEY` setting"
                    " in a `rose-suite.conf` file."
                    " Can be used to disable a setting using the syntax"
                    " `--define=[SECTION]!KEY` or"
                    " even `--define=[!SECTION]`."),
                action="append", default=[], dest="defines",
                sources={'cylc-rose'}),
            OptionSettings(
                ["--rose-template-variable", '-S', '--define-suite'],
                help=(
                    "As `--define`, but with an implicit `[SECTION]` for"
                    " workflow variables."),
                action="append", default=[], dest="rose_template_vars",
                sources={'cylc-rose'},
            )
        ]

    def add_cylc_rose_options(self) -> None:
        """Add extra options for cylc-rose plugin if it is installed.

        Now a vestigal interface for get_cylc_rose_options.
        """
        for option in self.get_cylc_rose_options():
            self.add_option(*option.args, **option.kwargs)

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


def appendif(list_, item):
    """Avoid duplicating items in output list"""
    if item not in list_:
        list_.append(item)
    return list_


def combine_options_pair(first_list, second_list):
    """Combine two option lists recording where each came from.

    Scenarios:
        - Arguments are identical - return this argument.
        - Arguments are not identical but have some common label strings,
          i.e. both arguments can be invoked using `-f`.
          - If there are non-shared label strings strip the shared ones.
          - Otherwise raise an error.
          E.g: If `command-A` has an option `-f` or `--file` and
          `command-B has an option `-f` or `--fortran`` then
          `command-A+B` will have options `--fortran` and `--file` but _not_
          `-f`, which would be confusing.
        - Arguments only apply to a single component of the compound CLI
          script.

    """
    output = []
    if not first_list:
        output = second_list
    elif not second_list:
        output = first_list
    else:
        for first, second in product(first_list, second_list):
            # Two options are identical in both args and kwargs:
            if first == second:
                first._update_sources(second)
                output = appendif(output, first)

            # If any of the argument names identical we must remove
            # overlapping names (if we can)
            # e.g. [-a, --aleph], [-a, --alpha-centuri] -> keep both options
            # but neither should have the `-a` short version:
            elif (
                first != second
                and first & second
            ):
                # if any of the args are different:

                if first.args == second.args:
                    raise Exception(
                        f'Clashing Options \n{first.args}\n{second.args}')
                else:
                    first_args = first - second
                    second.args = second - first
                    first.args = first_args
                    output = appendif(output, first)
                    output = appendif(output, second)
            else:
                # Neither option appears in the other list, so it can be
                # appended:
                if not first._in_list(second_list):
                    output = appendif(output, first)
                if not second._in_list(first_list):
                    output = appendif(output, second)

    return output


def add_sources_to_helps(
    options: Iterable[OptionSettings], modify: Optional[dict] = None
) -> None:
    """Get list of CLI commands this option applies to
    and prepend that list to the start of help.

    Arguments:
        options:
            List of OptionSettings to modify help upon.
        modify:
            Dict of items to substitute: Intended to allow one
            to replace cylc-rose with the names of the sub-commands
            cylc rose options apply to.
    """
    modify = {} if modify is None else modify
    for option in options:
        if hasattr(option, 'sources'):
            sources = list(option.sources)
            for match, sub in modify.items():
                if match in option.sources:
                    sources.append(sub)
                    sources.remove(match)

            option.kwargs['help'] = (
                f'<cyan>[{", ".join(sources)}]</cyan>'
                f' {option.kwargs["help"]}'
            )


def combine_options(
    *args: List[OptionSettings], modify: Optional[dict] = None
) -> List[OptionSettings]:
    """Combine lists of Cylc options.

    Ordering should be irrelevant because combine_options_pair should
    be commutative, and the overall order of args is not relevant.
    """
    output = args[0]
    for arg in args[1:]:
        output = combine_options_pair(arg, output)

    add_sources_to_helps(output, modify)
    return output


def cleanup_sysargv(
    script_name: str,
    workflow_id: str,
    options: 'Values',
    compound_script_opts: Iterable['OptionSettings'],
    script_opts: Iterable['OptionSettings'],
    source: str,
) -> None:
    """Remove unwanted options from sys.argv

    Some cylc scripts (notably Cylc Play when it is re-invoked on a scheduler
    server) require the correct content in sys.argv: This function
    subtracts the unwanted options from sys.argv.

    Args:
        script_name:
            Name of the target script. For example if we are
            using this for the play step of cylc vip then this
            will be "play".
        workflow_id:
        options:
            Actual options provided to the compound script.
        compound_script_options:
            Options available in compound script.
        script_options:
            Options available in target script.
        source:
            Source directory.
    """
    # Organize Options by dest.
    script_opts_by_dest = {
        x.kwargs.get('dest', x.args[0].strip(DOUBLEDASH)): x
        for x in script_opts
    }
    compound_opts_by_dest = {
        x.kwargs.get('dest', x.args[0].strip(DOUBLEDASH)): x
        for x in compound_script_opts
    }

    # Get a list of unwanted args:
    unwanted_compound: List[str] = []
    unwanted_simple: List[str] = []
    for unwanted_dest in set(options.__dict__) - set(script_opts_by_dest):
        for unwanted_arg in compound_opts_by_dest[unwanted_dest].args:
            if (
                compound_opts_by_dest[unwanted_dest].kwargs.get('action', None)
                in ['store_true', 'store_false']
            ):
                unwanted_simple.append(unwanted_arg)
            else:
                unwanted_compound.append(unwanted_arg)

    new_args = filter_sysargv(sys.argv, unwanted_simple, unwanted_compound)

    # replace compound script name:
    new_args[1] = script_name

    # replace source path with workflow ID.
    if str(source) in new_args:
        new_args.remove(str(source))
    if workflow_id not in new_args:
        new_args.append(workflow_id)

    sys.argv = new_args


def filter_sysargv(
    sysargs, unwanted_simple: List, unwanted_compound: List
) -> List:
    """Create a copy of sys.argv without unwanted arguments:

    Cases:
        >>> this = filter_sysargv
        >>> this(['--foo', 'expects-a-value', '--bar'], [], ['--foo'])
        ['--bar']
        >>> this(['--foo=expects-a-value', '--bar'], [], ['--foo'])
        ['--bar']
        >>> this(['--foo', '--bar'], ['--foo'], [])
        ['--bar']
    """
    pop_next: bool = False
    new_args: List = []
    for this_arg in sysargs:
        parts = this_arg.split('=', 1)
        if pop_next:
            pop_next = False
            continue
        elif parts[0] in unwanted_compound:
            # Case --foo=value or --foo value
            if len(parts) == 1:
                # --foo value
                pop_next = True
            continue
        elif parts[0] in unwanted_simple:
            # Case --foo does not expect a value:
            continue
        else:
            new_args.append(this_arg)
    return new_args


def log_subcommand(*args):
    """Log a command run as part of a sequence.

    Example:
        >>> log_subcommand('ruin', 'my_workflow')
        \x1b[1m\x1b[36m$ cylc ruin my_workflow\x1b[0m\x1b[1m\x1b[0m\n
    """
    # Args might be posixpath or similar.
    args = [str(a) for a in args]
    print(cparse(
        f'<b><cyan>$ cylc {" ".join(args)}</cyan></b>'
    ))
