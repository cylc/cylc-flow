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
"""Cylc configuration linter.

Checks code style, deprecated syntax and other issues."""
# NOTE: docstring needed for `cylc help all` output
# (if editing check this still comes out as expected)

COP_DOC = """cylc lint [OPTIONS] ARGS

Check .cylc and .rc files for code style, deprecated syntax and other issues.

By default, suggestions are written to stdout.

In-place mode ( "-i, --inplace") writes suggestions into the file as comments.
Commit to version control before using this, in case you want to back out.

"""
from colorama import Fore
from optparse import Values
from pathlib import Path
import re
from typing import Generator

from cylc.flow import LOG
from cylc.flow.option_parsers import (
    CylcOptionParser as COP,
)
from cylc.flow.cfgspec.workflow import upg, SPEC
from cylc.flow.parsec.config import ParsecConfig
from cylc.flow.terminal import cli_function
from cylc.flow.workflow_files import check_flow_file

STYLE_GUIDE = (
    'https://cylc.github.io/cylc-doc/latest/html/workflow-design-guide/'
    'style-guide.html#'
)
URL_STUB = "https://cylc.github.io/cylc-doc/latest/html/7-to-8/"
SECTION2 = r'\[\[\s*{}\s*\]\]'
SECTION3 = r'\[\[\[\s*{}\s*\]\]\]'
FILEGLOBS = ['*.rc', '*.cylc']
JINJA2_SHEBANG = '#!jinja2'
DEPENDENCY_SECTION_MSG = {
    'text': (
        '"[scheduling][dependencies][<recurrence>]graph =" -> '
        '"[scheduling][graph]<recurrence> ="'
    ),
    'rst': (
        '``[scheduling][dependencies][<recurrence>]graph =`` -> '
        '``[scheduling][graph]<recurrence> =``'
    )
}
JOBANDREMOTE_SECTION_MSG = {
    'text': (
        'settings in "[runtime][<namespace>][{}]" have been moved to '
        '"[runtime][<namespace>]" and "global.cylc[platforms]'
        '[<platforms name>]"'
    ),
    'rst': (
        'settings in ``[runtime][<namespace>][{}]`` have been moved to '
        '``[runtime][<namespace>]`` and ``global.cylc[platforms]'
        '[<platforms name>]``'
    )
}
JINJA2_FOUND_WITHOUT_SHEBANG = 'jinja2 found: no shebang (#!jinja2)'
CHECKS_DESC = {'U': '7 to 8 upgrades', 'S': 'Style'}
STYLE_CHECKS = {
    re.compile(r'^\t'): {
        'short': 'Use multiple spaces, not tabs',
        'url': STYLE_GUIDE + 'tab-characters'
    },
    # Not a full test, but if a non section is not indented...
    re.compile(r'^[^\{\[|\s]'): {
        'short': 'Item not indented.',
        'url': STYLE_GUIDE + 'indentation'
    },
    #            [section]
    re.compile(r'^\s+\[[^\[.]*\]'): {
        'short': 'Top level sections should not be indented.',
        'url': STYLE_GUIDE + 'indentation'
    },
    # 2 or 4 space indentation both seem reasonable:
    re.compile(r'^(|\s|\s{2,3}|\s{5,})\[\[[^\[.]*\]\]'): {
        'short': (
            'Second level sections should be indented exactly '
            '4 spaces.'
        ),
        'url': STYLE_GUIDE + 'indentation'
    },
    re.compile(r'^(|\s{1,7}|\s{9,})\[\[\[[^\[.]*\]\]\]'): {
        'short': (
            'Third level sections should be indented exactly '
            '8 spaces.'
        ),
        'url': STYLE_GUIDE + 'indentation'
    },
    re.compile(r'\s$'): {
        'short': 'trailing whitespace.',
        'url': STYLE_GUIDE + 'trailing-whitespace'
    },
    # Consider re-adding this as an option later:
    # re.compile(r'^.{80,}'): {
    #     'short': 'line > 79 characters.',
    #     'url': STYLE_GUIDE + 'line-length-and-continuation'
    # },
    re.compile(r'inherit\s*=\s*[a-z].*$'): {
        'short': 'Family name contains lowercase characters.',
        'url': STYLE_GUIDE + 'task-naming-conventions'
    },
}
# Subset of deprecations which are tricky (impossible?) to scrape from the
# upgrader.
MANUAL_DEPRECATIONS = {
    re.compile(SECTION2.format('dependencies')): {
        'short': DEPENDENCY_SECTION_MSG['text'],
        'url': '',
        'rst': DEPENDENCY_SECTION_MSG['rst']
    },
    re.compile(r'graph\s*=\s*'): {
        'short': DEPENDENCY_SECTION_MSG['text'],
        'url': '',
        'rst': DEPENDENCY_SECTION_MSG['rst']
    },
    re.compile(SECTION3.format('remote')): {
        'short': JOBANDREMOTE_SECTION_MSG['text'].format('remote'),
        'url': '',
        'rst': JOBANDREMOTE_SECTION_MSG['rst'].format('remote')
    },
    re.compile(SECTION3.format('job')): {
        'short': JOBANDREMOTE_SECTION_MSG['text'].format('job'),
        'url': '',
        'rst': JOBANDREMOTE_SECTION_MSG['rst'].format('job')
    },
    re.compile(r'batch system\s*=\s*'): {
        'short': (
            'flow.cylc[runtime][<namespace>][job]batch system -> '
            'global.cylc[platforms][<platform name>]job runner'
        ),
        'url': '',
        'rst': (
            '``flow.cylc[runtime][<namespace>][job]batch system`` -> '
            '``global.cylc[platforms][<platform name>]job runner``'
        )
    },
}


def list_to_config(path_, is_section=False):
    """Prettify a config list

    Args:
        path_: list forming address in the config.
        is_section: Is this item a section?

    Examples:
        >>> list_to_config(['foo', 'bar'], False)
        '[foo]bar'

        >>> list_to_config(['foo', 'bar'], True)
        '[foo][bar]'
    """
    output = ''
    for item in path_[:-1]:
        # All but the last item must be sections:
        output += f'[{item}]'
    if is_section:
        # Last item is section:
        output += f'[{path_[-1]}]'
    else:
        # Last item not a section:
        output += path_[-1]
    return output


def get_upgrader_info():
    """Extract info about obseletions and deprecations from Parsec Objects."""
    conf = ParsecConfig(SPEC, upg)
    upgrades = conf.upgrader(conf.dense, '').upgrades
    deprecations = {}

    for _, upgrades_for_version in upgrades.items():
        for upgrade in upgrades_for_version:
            # Set a flag indicating that a variable has been moved.
            if upgrade['new'] is None:
                section_name = list_to_config(
                    upgrade["old"], upgrade["is_section"])
                short = f'{section_name} - not available at Cylc 8'
                rst = f'``{section_name}`` is not available at Cylc 8'
            elif upgrade["old"][-1] == upgrade['new'][-1]:
                # Where an item with the same name has been moved
                # a 1 line regex isn't going to work.
                continue
            else:
                old = list_to_config(
                    upgrade["old"], upgrade["is_section"])
                new = list_to_config(
                    upgrade["new"], upgrade["is_section"])
                short = f'{old} -> {new}'
                rst = f'``{old}`` is now ``{new}``'

            # Check whether upgrade is section:
            if upgrade['is_section'] is True:
                section_depth = len(upgrade['old'])
                start = r'\[' * section_depth
                end = r'\]' * section_depth
                name = upgrade["old"][-1]
                regex = re.compile(fr'{start}\s*{name}\s*{end}\s*$')
            else:
                name = upgrade["old"][-1]
                expr = rf'{name}\s*=\s*.*'
                regex = re.compile(expr)

            deprecations[regex] = {
                'short': short,
                'url': '',
                'rst': rst,
            }
    # Some deprecations are not specified in a straightforward to scrape
    # way and these are specified in MANUAL_DEPRECATIONS:
    deprecations.update(MANUAL_DEPRECATIONS)
    return deprecations


def get_checkset_from_name(name):
    """Take a ruleset name and return a ruleset code

    Examples:
        >>> get_checkset_from_name('728')
        ['U']
        >>> get_checkset_from_name('style')
        ['S']
        >>> get_checkset_from_name('all')
        ['U', 'S']
    """
    if name == '728':
        purpose_filters = ['U']
    elif name == 'style':
        purpose_filters = ['S']
    else:
        purpose_filters = ['U', 'S']
    return purpose_filters


def parse_checks(check_arg):
    """Collapse metadata in checks dicts.
    """
    parsedchecks = {}
    purpose_filters = get_checkset_from_name(check_arg)

    checks = {'U': get_upgrader_info(), 'S': STYLE_CHECKS}

    for purpose, ruleset in checks.items():
        if purpose in purpose_filters:
            for index, (pattern, meta) in enumerate(ruleset.items(), start=1):
                meta.update({'purpose': purpose})
                meta.update({'index': index})
                parsedchecks.update({pattern: meta})
    return parsedchecks


def check_cylc_file(dir_, file_, checks, modify=False):
    """Check A Cylc File for Cylc 7 Config"""
    file_rel = file_.relative_to(dir_)
    # Set mode as read-write or read only.
    outlines = []

    # Open file, and read it's line to memory.
    lines = file_.read_text().split('\n')
    jinja_shebang = lines[0].strip().lower() == JINJA2_SHEBANG
    count = 0
    for line_no, line in enumerate(lines, start=1):
        for check, message in checks.items():
            # Tests with for presence of Jinja2 if no shebang line is
            # present.
            if (
                jinja_shebang
                and message['short'].startswith(
                    JINJA2_FOUND_WITHOUT_SHEBANG)
            ):
                continue

            if check.findall(line) and not line.strip().startswith('#'):
                count += 1
                if modify:
                    if message['url'].startswith('http'):
                        url = message['url']
                    else:
                        url = URL_STUB + message['url']
                    outlines.append(
                        f'# [{message["purpose"]}{message["index"]:03d}]: '
                        f'{message["short"]}\n'
                        f'# - see {url}'
                    )
                else:
                    print(
                        Fore.YELLOW +
                        f'[{message["purpose"]}{message["index"]:03d}]'
                        f' {file_rel}:{line_no}: {message["short"]}'
                    )
        if modify:
            outlines.append(line)
    if modify:
        file_.write_text('\n'.join(outlines))
    return count


def get_cylc_files(base: Path) -> Generator[Path, None, None]:
    """Given a directory yield paths to check."""
    for rglob in FILEGLOBS:
        for path in base.rglob(rglob):
            # Exclude log directory:
            if path.relative_to(base).parts[0] != 'log':
                yield path


def get_reference_rst(checks):
    """Print a reference for checks to be carried out.

    Returns:
        RST compatible text.
    """
    output = ''
    current_checkset = ''
    for check, meta in checks.items():
        # Check if the purpose has changed - if so create a new
        # section title:
        if meta['purpose'] != current_checkset:
            current_checkset = meta['purpose']
            title = CHECKS_DESC[meta["purpose"]]
            output += f'\n{title}\n{"-" * len(title)}\n\n'

        # Fill a template with info about the issue.
        template = (
            '{checkset}{index:003d}\n^^^^\n{summary}\n\n'
        )
        if meta['url'].startswith('http'):
            url = meta['url']
        else:
            url = URL_STUB + meta['url']
        summary = meta.get("rst", meta['short'])
        msg = template.format(
            title=check.pattern.replace('\\', ''),
            checkset=meta['purpose'],
            summary=summary,
            url=url,
            index=meta['index'],
        )
        output += msg
    output += '\n'
    return output


def get_reference_text(checks):
    """Print a reference for checks to be carried out.

    Returns:
        RST compatible text.
    """
    output = ''
    current_checkset = ''
    for check, meta in checks.items():
        # Check if the purpose has changed - if so create a new
        # section title:
        if meta['purpose'] != current_checkset:
            current_checkset = meta['purpose']
            title = CHECKS_DESC[meta["purpose"]]
            output += f'\n{title}\n{"-" * len(title)}\n\n'

        # Fill a template with info about the issue.
        template = (
            '{checkset}{index:003d}:\n    {summary}\n\n'
        )
        if meta['url'].startswith('http'):
            url = meta['url']
        else:
            url = URL_STUB + meta['url']
        msg = template.format(
            title=check.pattern.replace('\\', ''),
            checkset=meta['purpose'],
            summary=meta['short'],
            url=url,
            index=meta['index'],
        )
        output += msg
    output += '\n'
    return output


def get_option_parser() -> COP:
    parser = COP(
        COP_DOC,
        argdoc=[COP.optional(('DIR ...', 'Directories to lint'))],
    )
    parser.add_option(
        '--inplace', '-i',
        help=(
            'Modify files in place, adding comments to files. '
            'If not set, the script will work as a linter'
        ),
        action='store_true',
        default=False,
    )
    parser.add_option(
        '--ruleset', '-r',
        help=(
            'Set of rules to use: '
            '("728", "style", "all")'
        ),
        default='all',
        choices=('728', 'style', 'all'),
        dest='linter'
    )
    parser.add_option(
        '--list-codes',
        help=(
            'List all linter codes.'
        ),
        action='store_true',
        default=False,
        dest='ref_mode'
    )

    return parser


@cli_function(get_option_parser)
def main(parser: COP, options: 'Values', *targets) -> None:
    if options.ref_mode:
        print(get_reference_text(parse_checks(options.linter)))
        exit(0)

    # Expand paths so that message will return full path
    # & ensure that CWD is used if no path is given:
    if targets:
        targets = tuple(Path(path).resolve() for path in targets)
    else:
        targets = (str(Path.cwd()),)

    # make sure the targets are all src/run directories
    for target in targets:
        check_flow_file(target)

    # Get a list of checks bas ed on the checking options:
    # Allow us to check any number of folders at once
    for target in targets:
        count = 0
        target = Path(target)
        if not target.exists():
            LOG.warn(f'Path {target} does not exist.')
        else:
            # Check whether target is an upgraded Cylc 8 workflow.
            # If it isn't then we shouldn't run the 7-to-8 checks upon
            # it:
            cylc8 = (target / 'flow.cylc').exists()
            if not cylc8 and options.linter == '728':
                LOG.error(
                    f'{target} not a Cylc 8 workflow: '
                    'Lint after renaming '
                    '"suite.rc" to "flow.cylc"'
                )
                continue
            elif not cylc8 and options.linter == 'all':
                check_names = 'style'
            else:
                check_names = options.linter

            # Check each file:
            checks = parse_checks(check_names)
            for file_ in get_cylc_files(target):
                LOG.debug(f'Checking {file_}')
                count += check_cylc_file(
                    target,
                    file_,
                    checks,
                    options.inplace,
                )

        if count > 0:
            msg = (
                f'\n{Fore.YELLOW}'
                f'Checked {target} against {check_names} checks'
                f'rules and found {count} issue'
                f'{"s" if count > 1 else ""}.'
            )
        else:
            msg = (
                f'{Fore.GREEN}'
                f'Checked {target} against {check_names} checks'
                'Found no issues.'
            )

        print(msg)


# NOTE: use += so that this works with __import__
# (docstring needed for `cylc help all` output)
__doc__ += get_reference_text(parse_checks('all'))
