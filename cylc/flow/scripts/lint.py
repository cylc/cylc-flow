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
"""Cylc 728 looks through one or more folders for ``suite*.rc`` files and
search for Cylc 7 syntax which may be problematic at Cylc 8.

Can be run either as a linter or "in place" (``-i``), leaving comments
in files. If used in the "in place" mode it is recommended that you ensure
that you have recorded the state of your workflow in a version control
system before starting.

.. warning::

   When run with ``-i`` (``--inplace``) mode ``Cylc 728`` changes your files.
   We strongly recommend committing your workflow to version control
   before using ``Cylc 728 -i``.

Usage
^^^^^

.. code-block:: bash

   # run as a linter
   cylc 728 <paths to workflow directories to check>

   # run inplace
   cylc 728 --inplace <paths to workflow directories to check>
   cylc 728 -i <paths to workflow directories to check>

   # Get information about errors:
   cylc 728 --reference
   cylc 728 -r

Change Codes
^^^^^^^^^^^^

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
CHECKS = {
    'U': {
        re.compile(SECTION1.format('visualization')): {
            'short': 'section ``[visualization]`` has been removed.',
            'url': 'summary.html#new-web-and-terminal-uis'
        },
        re.compile(SECTION1.format('cylc')): {
            'short': 'section ``[cylc]`` is now called ``[scheduler]``.',
            'url': 'summary.html#terminology'
        },
        re.compile(SECTION2.format('authentication')): {
            'short': '``[cylc][authentication]`` is now obsolete.',
            'url': ''
        },
        re.compile(r'^\s*include at start-up\s*='): {
            'short': '``[cylc]include at start up`` is obsolete.',
            'url': (
                'major-changes/excluding-tasks.html?'
                '#excluding-tasks-at-start-up-is-not-supported'
            ),
        },
        re.compile(r'exclude at start-up\s*?='): {
            'short': '``[cylc]exclude at start up`` is obsolete.',
            'url': (
                'major-changes/excluding-tasks.html?'
                '#excluding-tasks-at-start-up-is-not-supported'
            ),
        },
        re.compile(r'log resolved dependencies\s*?='): {
            # Mainly for testing
            'short': '``[cylc]log resolved dependencies`` is obsolete.',
            'url': ''
        },
        re.compile(r'required run mode\s*?='): {
            # Mainly for testing
            'short': '``[cylc]required run mode`` is obsolete.',
            'url': ''
        },
        re.compile(r'health check interval\s*?='): {
            'short': '``[cylc]health check interval`` is obsolete.',
            'url': ''
        },
        re.compile(r'abort if any task fails\s*?='): {
            'short': '``[cylc]abort if any task fails`` is obsolete.',
            'url': ''
        },
        re.compile(r'disable automatic shutdown\s*?='): {
            'short': '``[cylc]disable automatic shutdown`` is obsolete.',
            'url': ''
        },
        re.compile(r'reference test\s*?='): {
            # Mainly for testing
            'short': '``[cylc]reference test`` is obsolete.',
            'url': ''
        },
        re.compile(r'disable suite event handlers\s*?='): {
            'short': '``[cylc]disable suite event handlers`` is obsolete.',
            'url': ''
        },
        re.compile(SECTION2.format('simulation')): {
            'short': '``[cylc]simulation`` is obsolete.',
            'url': ''
        },
        re.compile(r'spawn to max active cycle points\s*?='): {
            'short': '``[cylc]spawn to max active cycle points`` is obsolete.',
            'url': (
                'https://cylc.github.io/cylc-doc/latest/html/reference'
                '/config/workflow.html#flow.cylc[scheduling]runahead%20limit'
            ),
        },
        re.compile(r'abort on stalled\s*?='): {
            'short':
                '``[cylc][events]abort on stalled`` is obsolete.',
            'url': ''
        },
        re.compile(r'abort if .* handler fails\s*?='): {
            'short': (
                '``[cylc][events]abort if ___ handler fails`` commands are'
                ' obsolete.'
            ),
            'url': ''
        },
        re.compile(r'mail to\s*='): {
            'short': (
                '``[events]mail to`` => ``[mail]to``'
            ),
            'url': ''
        },
        re.compile(r'mail from\s*='): {
            'short': (
                '``[events]mail from`` => ``[mail]from``'
            ),
            'url': ''
        },
        re.compile(r'mail footer\s*='): {
            'short': (
                '``[events]mail footer`` => ``[mail]footer``'
            ),
            'url': ''
        },
        re.compile(r'mail smtp\s*='): {
            'short': (
                '``[events]mail smtp`` => ``global.cylc[scheduler][mail]smtp``'
            ),
            'url': ''
        },
        re.compile(r'^\s*timeout\s*='): {
            'short': (
                '``[cylc][events]timeout`` => '
                '``[scheduler][events]stall timeout``'
            ),
            'url': ''
        },
        re.compile(r'^\s*inactivity\s*='): {
            'short': (
                '``[cylc][events]inactivity`` => '
                '``[scheduler][events]inactivity timeout``'
            ),
            'url': ''
        },
        re.compile(r'abort on inactivity\s*='): {
            'short': (
                '``[cylc][events]abort on inactivity`` => '
                '``[scheduler][events]abort on inactivity timeout``'
            ),
            'url': ''
        },
        re.compile(r'force run mode\s*='): {
            'short': (
                '``[cylc]force run mode`` is obsolete.'
            ),
            'url': ''
        },
        re.compile(SECTION2.format('environment')): {
            'short': (
                '``[cylc][environment]`` is obsolete.'
            ),
            'url': ''
        },
        re.compile(r'.* handler\s*?='): {
            'short': (
                '``[cylc][<namespace>][events]___ handler`` commands are'
                ' now "handlers".'
            ),
            'url': ''
        },
        re.compile(r'mail retry delays\s*?='): {
            'short': (
                '``[runtime][<namespace>][events]mail retry delays`` '
                'is obsolete.'
            ),
            'url': ''
        },
        re.compile(r'extra log files\s*?='): {
            'short': (
                '``[runtime][<namespace>][events]extra log files`` '
                'is obsolete.'
            ),
            'url': ''
        },
        re.compile(r'shell\s*?='): {
            'short': (
                '``[runtime][<namespace>]shell`` '
                'is obsolete.'
            ),
            'url': ''
        },
        re.compile(r'suite definition directory\s*?='): {
            'short': (
                '``[runtime][<namespace>][remote]suite definition directory`` '
                'is obsolete.'
            ),
            'url': 'summary.html#symlink-dirs'
        },
        re.compile(SECTION2.format('dependencies')): {
            'short': '``[dependencies]`` is deprecated.',
            'url': 'major-changes/config-changes.html#graph'
        },
        re.compile(r'graph\s*?='): {
            'short': (
                '``[cycle point]graph =`` is deprecated, '
                'use ``cycle point = <graph>``'
            ),
            'url': 'major-changes/config-changes.html#graph'
        },
        re.compile(SECTION2.format('remote')): {
            'short': (
                '``[runtime][<namespace>][remote]host`` is deprecated, '
                'use ``[runtime][<namespace>]platform``'
            ),
            'url': 'major-changes/platforms.html#platforms'
        },
        re.compile(r'suite state polling\s*='): {
            'short': (
                '``[runtime][<namespace>]suite state polling`` is deprecated, '
                'use ``[runtime][<namespace>]workflow state polling``'
            ),
            'url': 'major-changes/platforms.html#platforms'
        },
        re.compile(SECTION3.format('job')): {
            'short': (
                '``[runtime][<namespace>][job]`` is deprecated, '
                'use ``[runtime][<namespace>]platform``'
                '\n    (the following items can be moved to '
                '``[runtime][<namespace>]``:'
                '\n    - ``execution retry delays``'
                '\n    - ``submission retry delays``'
                '\n    - ``execution polling intervals``'
                '\n    - ``submission polling intervals``'
                '\n    - ``execution time limit``'
            ),
            'url': 'major-changes/platforms.html#platforms'
        },
        re.compile(SECTION2.format('parameter templates')): {
            'short': (
                '``[cylc][parameter templates]`` is deprecated, '
                'use ``[task parameters][templates]``'
            ),
            'url': ''
        },
        re.compile(SECTION2.format('parameters')): {
            'short': (
                '``[cylc][parameters]`` is deprecated, '
                'use ``[task parameters]``'
            ),
            'url': ''
        },
        re.compile(r'task event mail interval\s*?='): {
            'short': (
                '``[cylc][task event mail interval]`` is deprecated, '
                'use ``[scheduler][mail][task event batch interval]``'
            ),
            'url': ''
        },
        re.compile(r'{{.*}}'): {
            'short': (
                f'{JINJA2_FOUND_WITHOUT_SHEBANG}'
                '{{VARIABLE}}'
            ),
            'url': ''
        },
        re.compile(r'{%.*%}'): {
            'short': (
                f'{JINJA2_FOUND_WITHOUT_SHEBANG}'
                '{% .* %}'
            ),
            'url': ''
        },
        re.compile(r'max active cycle points\s*='): {
            'short': (
                '``[scheduling]max active cycle points`` is deprecated'
                'use [scheduling]runahead limit'
            ),
            'url': ''
        },
        re.compile(r'hold after point\s*='): {
            'short': (
                '``[scheduling]hold after point`` is deprecated'
                'use [scheduling]hold after cycle point'
            ),
            'url': ''
        },
    },
    'S': {
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
}


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

    for purpose, checks in CHECKS.items():
        if purpose in purpose_filters:
            for index, (pattern, meta) in enumerate(checks.items()):
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


def get_reference(checks):
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
            '{checkset}{index:003d} ``{title}``:\n    {summary}\n'
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
        __doc__,
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

    return parser


@cli_function(get_option_parser)
def main(parser: COP, options: 'Values', *targets) -> None:

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
        else:
            color = Fore.GREEN
        msg = (
            f'Checked {target} against {check_names} '
            f'rules and found {count} issues.'
        )
        print(f'{color}{"-" * len(msg)}\n{msg}')


__doc__ += get_reference(parse_checks('all'))
