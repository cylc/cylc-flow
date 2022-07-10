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
COP_DOC = """Cylc lint looks through one or more folders for
"*.cylc" and "*.rc" files and
search for Cylc 7 syntax which may be problematic at Cylc 8.

Can be run either as a linter or "in place" ("-i"), leaving comments
in files.

When run with ``-i`` (``--inplace``) mode ``Cylc lint`` changes your files.
We strongly recommend committing your workflow to version control
before using ``Cylc lint -i``.

Usage

# run as a linter
cylc lint <paths to workflow directories to check>

# run inplace
cylc lint --inplace <paths to workflow directories to check>
cylc lint -i <paths to workflow directories to check>

# Get information about errors:
cylc lint --reference
cylc lint -r
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
from cylc.flow.terminal import cli_function

STYLE_GUIDE = (
    'https://cylc.github.io/cylc-doc/latest/html/workflow-design-guide/'
    'style-guide.html#'
)
URL_STUB = "https://cylc.github.io/cylc-doc/latest/html/7-to-8/"
SECTION1 = r'\[\s*{}\s*\]'
SECTION2 = r'\[\[\s*{}\s*\]\]'
SECTION3 = r'\[\[\[\s*{}\s*\]\]\]'
FILEGLOBS = ['*.rc', '*.cylc']
JINJA2_SHEBANG = '#!jinja2'
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
    re.compile(r'^\s+\[.*\]'): {
        'short': 'Too many indents for top level section.',
        'url': STYLE_GUIDE + 'indentation'
    },
    # 2 or 4 space indentation both seem reasonable:
    re.compile(r'^(\s|\s{3}|\s{5,})\[\[.*\]\]'): {
        'short': 'wrong number of indents for second level section.',
        'url': STYLE_GUIDE + 'indentation'
    },
    re.compile(r'^(\s{1,3}|\s{5,7}|\s{9,})\[\[\[.*\]\]\]'): {
        'short': 'wrong number of indents for third level section.',
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


def list_to_config(path_):
    """Prettify a config list"""
    output = ''
    for item in path_[:-1]:
        output += f'[{item}]'
    output += path_[-1]
    return output


def get_upgrader_info():
    """Extract info about obseletions and deprecations from Parsec Objects."""
    from cylc.flow.cfgspec.workflow import upg, SPEC
    from cylc.flow.parsec.config import ParsecConfig
    conf = ParsecConfig(SPEC, upg)
    upgrades = conf.upgrader(conf.dense, '').upgrades
    deprecations = {}

    for _, upgrades_for_version in upgrades.items():
        for upgrade in upgrades_for_version:
            # Set a flag indicating that a variable has been moved.
            if upgrade['new'] is None:
                short = (
                    f'{list_to_config(upgrade["old"])} is not '
                    'available at Cylc 8'
                )
            elif upgrade["old"][-1] == upgrade['new'][-1]:
                # Where an item with the same name has been moved
                # a 1 line regex isn't going to work.
                continue
            else:
                short = (
                    f'{list_to_config(upgrade["old"])} is now '
                    f'{list_to_config(upgrade["new"])}'
                )

            # Check whether upgrade is section:
            if upgrade['is_section'] is True:
                section_depth = len(upgrade['old'])
                start = r'\[' * section_depth
                end = r'\]' * section_depth
                name = upgrade["old"][-1]
                regex = re.compile(fr'{start}\s*{name}\s*{end}')
            else:
                name = upgrade["old"][-1]
                expr = rf'{name}\s*=\s*.*'
                regex = re.compile(expr)

            deprecations[regex] = {
                'short': short,
                'url': '',
            }
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


def check_cylc_file(file_, checks, modify=False):
    """Check A Cylc File for Cylc 7 Config"""
    # Set mode as read-write or read only.
    outlines = []

    # Open file, and read it's line to mempory.
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
                        f'{file_}: {line_no}: {message["short"]}'
                    )
        if modify:
            outlines.append(line)
    if modify:
        file_.write_text('\n'.join(outlines))
    return count


def get_cylc_files(base: Path) -> Generator[Path, None, None]:
    """Given a directory yield paths to check.
    """
    excludes = [Path('log')]

    for rglob in FILEGLOBS:
        for path in base.rglob(rglob):
            # Exclude log directory:
            if path.relative_to(base).parents[0] not in excludes:
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
            '{checkset}{index:003d}\n^^^^\n{summary}\n'
            'see - {url}\n\n'
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
            '{checkset}{index:003d}:\n    {summary}\n'
            '    see - {url}\n'
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
        default='728',
        choices=('728', 'style', 'all'),
        dest='linter'
    )
    parser.add_option(
        '--reference', '--ref', '-R',
        help=(
            'Print Reference for error codes.'
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

    # Get a list of checks bas ed on the checking options:
    count = 0
    # Allow us to check any number of folders at once
    for target in targets:
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
                    'No checks will be made.'
                )
                continue
            elif not cylc8 and options.linter == 'all':
                LOG.error(
                    f'{target} not a Cylc 8 workflow: '
                    'Checking only for style.'
                )
                check_names = parse_checks('style')
            else:
                check_names = options.linter

            # Check each file:
            checks = parse_checks(check_names)
            for file_ in get_cylc_files(target):
                LOG.debug(f'Checking {file_}')
                count += check_cylc_file(file_, checks, options.inplace)

        # Summing up:
        if count > 0:
            color = Fore.YELLOW
            exit(1)
        else:
            color = Fore.GREEN
        msg = (
            f'Checked {target} against {check_names} '
            f'rules and found {count} issues.'
        )
        print(f'{color}{"-" * len(msg)}\n{msg}')


__doc__ = get_reference_rst(parse_checks('all'))
