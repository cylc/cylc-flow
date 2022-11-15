#!/usr/bin/env python3

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

"""cylc install [OPTIONS] ARGS

Install a workflow into ~/cylc-run.

The workflow can then be started, stopped, and targeted by name.

Normal installation creates a numbered run directory
"~/cylc-run/<workflow-name>/run<number>".

If a SOURCE_NAME is supplied, Cylc will search for the workflow source in the
list of directories given by "global.cylc[install]source dirs", and install
the first match. The installed workflow name will be the same as SOURCE_NAME,
unless --workflow-name is used.

If a PATH is supplied, Cylc will install the workflow from the source directory
given by the path. Relative paths must start with "./" to avoid ambiguity with
SOURCE_NAME (i.e. "foo/bar" will be interpreted as a source name, whereas
"./foo/bar" will be interpreted as a path). The installed workflow name will
be the basename of the path, unless --workflow-name is used.

If no argument is supplied, Cylc will install the workflow from the source
in the current working directory.

A "_cylc-install/source" symlink to the source directory will be created in
"~/cylc-run/<workflow-name>". Any files or directories (excluding .git, .svn)
from the source directory are copied to the new run directory. A ".service"
directory will also be created in the run directory; this is used for server
authentication files at runtime.

Examples:
  # Install workflow "dogs/fido" from the first match in
  # `global.cylc[install]source dirs`, e.g. ~/cylc-src/dogs/fido/flow.cylc,
  # with run directory ~/cylc-run/dogs/fido/run1 (if "run1" already exists,
  # this will increment)
  $ cylc install dogs/fido

  # Install $PWD as "rabbit", if $PWD is ~/bunny/rabbit, with
  # run directory ~/cylc-run/rabbit/run1
  $ cylc install

  # Install $PWD as "rabbit", if $PWD is ~/bunny/rabbit, with
  # run directory ~/cylc-run/rabbit (note: no "run1" sub-directory)
  $ cylc install --no-run-name

  # Install $PWD as "fido", regardless of what $PWD is called, with
  # run directory ~/cylc-run/fido/run1
  $ cylc install --workflow-name=fido

  # Install $PWD/bunny/rabbit/ as "rabbit", with run directory
  # ~/cylc-run/rabbit/run1
  $ cylc install ./bunny/rabbit

  # Install /home/somewhere/badger as "badger", with run directory
  # ~/cylc-run/badger/run1
  $ cylc install /home/somewhere/badger

  # Install $PWD as "cats", if $PWD is ~/cats, with run directory
  # ~/cylc-run/cats/paws
  $ cylc install --run-name=paws

The same workflow can be installed with multiple names; this results in
multiple workflow run directories that link to the same workflow definition.
"""

from ansimarkup import ansiprint as cprint
import asyncio
from optparse import Values
from pathlib import Path
from typing import Optional, Dict, Any

from cylc.flow.scripts.scan import (
    get_pipe,
    _format_plain,
    FLOW_STATE_SYMBOLS,
    FLOW_STATE_CMAP
)
from cylc.flow import iter_entry_points
from cylc.flow.exceptions import PluginError, InputError
from cylc.flow.loggingutil import CylcLogFormatter
from cylc.flow.option_parsers import (
    CylcOptionParser as COP,
    OptionSettings,
    Options
)
from cylc.flow.pathutil import (
    EXPLICIT_RELATIVE_PATH_REGEX,
    expand_path,
    get_workflow_run_dir
)
from cylc.flow.workflow_files import (
    install_workflow,
    parse_cli_sym_dirs,
    search_install_source_dirs
)
from cylc.flow.terminal import cli_function


INSTALL_OPTIONS = [
    OptionSettings(
        ["--workflow-name", "-n"],
        help="Install into ~/cylc-run/<WORKFLOW_NAME>/runN ",
        action="store",
        metavar="WORKFLOW_NAME",
        default=None,
        dest="workflow_name",
        sources={'install'},
    ),
    OptionSettings(
        ["--symlink-dirs"],
        help=(
            "Enter a comma-delimited list, in the form"
            " 'log=path/to/store, share = $HOME/some/path, ...'."
            " Use this option to override the global.cylc configuration"
            " for local symlinks for the run, log, work, share and"
            " share/cycle directories. Enter"
            " an empty list '' to skip making localhost symlink dirs."),
        action="store",
        dest="symlink_dirs",
        sources={'install'},
    ),
    OptionSettings(
        ["--run-name"],
        help=(
            "Give the run a custom name instead of automatically"
            " numbering it."),
        action="store",
        metavar="RUN_NAME",
        default=None,
        dest="run_name",
        sources={'install'},
    ),
    OptionSettings(
        ["--no-run-name"],
        help=(
            "Install the workflow directly into"
            " ~/cylc-run/<workflow_name>,"
            " without an automatic run number or custom run name."),
        action="store_true",
        default=False,
        dest="no_run_name",
        sources={'install'},
    ),
    OptionSettings(
        ['--no-ping'],
        help=(
            "When scanning for active instances of the workflow, "
            "do not attempt to contact the schedulers to get status."),
        action='store_true',
        default=False,
        dest='no_ping',
        sources={'install'},
    )
]


def get_option_parser() -> COP:
    parser = COP(
        __doc__,
        comms=True,
        argdoc=[
            COP.optional(
                ('SOURCE_NAME | PATH',
                 'Workflow source name or path to source directory')
            )
        ]
    )

    options = parser.get_cylc_rose_options() + INSTALL_OPTIONS

    for option in options:
        parser.add_option(*option.args, **option.kwargs)

    return parser


def get_source_location(path: Optional[str]) -> Path:
    """Return the workflow source location as an absolute path.

    Note: does not check that the source actually exists.
    """
    if path is None:
        return Path.cwd()
    path = str(path).strip()
    expanded_path = Path(expand_path(path))
    if expanded_path.is_absolute():
        return expanded_path
    if EXPLICIT_RELATIVE_PATH_REGEX.match(path):
        return Path.cwd() / expanded_path
    return search_install_source_dirs(expanded_path)


async def scan(wf_name: str, ping: bool = True) -> None:
    """Print any instances of wf_name that are already active."""
    opts = Values({
        'name': [f'{wf_name}/*'],
        'states': {'running', 'paused', 'stopping'},
        'source': False,
        'ping': ping,  # get status of scanned workflows
    })
    active = [
        item async for item in get_pipe(
            opts, None,
            scan_dir=get_workflow_run_dir(wf_name)  # restricted scan
        )
    ]
    if active:
        n = len(active)
        grammar = (
            ["s", "are", "them all"]
            if n > 1 else
            ["", "is", "it"]
        )
        print(
            CylcLogFormatter.COLORS['WARNING'].format(
                f'NOTE: {n} run%s of "{wf_name}"'
                ' %s already active:' % tuple(grammar[:2])
            )
        )
        for item in active:
            if opts.ping:
                status = item['status']
                tag = FLOW_STATE_CMAP[status]
                symbol = f"  <{tag}>{FLOW_STATE_SYMBOLS[status]}</{tag}>"
            else:
                symbol = " "
            cprint(symbol, _format_plain(item, opts))
        pattern = (
            f"'{wf_name}/*'"
            if n > 1 else
            f"{item['name']}"
        )
        print(
            f'You can stop %s with:\n  cylc stop {pattern}'
            '\nSee "cylc stop --help" for options.' % grammar[-1]
        )


InstallOptions = Options(get_option_parser())


@cli_function(get_option_parser)
def main(
    _parser: COP,
    opts: 'Values',
    reg: Optional[str] = None
) -> None:
    """CLI wrapper."""
    install_cli(opts, reg)


def install_cli(
    opts: 'Values',
    reg: Optional[str] = None
) -> str:
    """Install workflow and scan for already-running instances."""
    wf_name = install(opts, reg)
    asyncio.run(
        scan(wf_name, not opts.no_ping)
    )
    return wf_name


def install(
    opts: 'Values', reg: Optional[str] = None
) -> str:
    if opts.no_run_name and opts.run_name:
        raise InputError(
            "options --no-run-name and --run-name are mutually exclusive."
        )
    source = get_source_location(reg)
    for entry_point in iter_entry_points(
        'cylc.pre_configure'
    ):
        try:
            entry_point.resolve()(srcdir=source, opts=opts)
        except Exception as exc:
            # NOTE: except Exception (purposefully vague)
            # this is to separate plugin from core Cylc errors
            raise PluginError(
                'cylc.pre_configure',
                entry_point.name,
                exc
            ) from None

    cli_symdirs: Optional[Dict[str, Dict[str, Any]]] = None
    if opts.symlink_dirs == '':
        cli_symdirs = {}
    elif opts.symlink_dirs:
        cli_symdirs = parse_cli_sym_dirs(opts.symlink_dirs)

    source_dir, rundir, workflow_name = install_workflow(
        source=source,
        workflow_name=opts.workflow_name,
        run_name=opts.run_name,
        no_run_name=opts.no_run_name,
        cli_symlink_dirs=cli_symdirs
    )

    for entry_point in iter_entry_points(
        'cylc.post_install'
    ):
        try:
            entry_point.resolve()(
                srcdir=source_dir,
                opts=opts,
                rundir=str(rundir)
            )
        except Exception as exc:
            # NOTE: except Exception (purposefully vague)
            # this is to separate plugin from core Cylc errors
            raise PluginError(
                'cylc.post_install',
                entry_point.name,
                exc
            ) from None
    return workflow_name
