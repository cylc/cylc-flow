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

Checks code style, deprecated syntax and other issues.

"""
# NOTE: docstring needed for `cylc help all` output
# (if editing check this still comes out as expected)

COP_DOC = """cylc lint [OPTIONS] ARGS

Check .cylc and .rc files for code style, deprecated syntax and other issues.

By default, suggestions are written to stdout.

In-place mode ("-i, --inplace") writes suggestions into the file as comments.
Commit to version control before using this, in case you want to back out.

A non-zero return code will be returned if any issues are identified.
This can be overridden by providing the "--exit-zero" flag.

Configurations for Cylc lint can also be set in a pyproject.toml file.

"""
from colorama import Fore
from optparse import Values
from pathlib import Path
import re
import sys
import tomli
from typing import Generator, Union

from cylc.flow import LOG
from cylc.flow.exceptions import CylcError
from cylc.flow.option_parsers import (
    CylcOptionParser as COP,
    WORKFLOW_ID_OR_PATH_ARG_DOC
)
from cylc.flow.cfgspec.workflow import upg, SPEC
from cylc.flow.id_cli import parse_id
from cylc.flow.parsec.config import ParsecConfig
from cylc.flow.terminal import cli_function

STYLE_GUIDE = (
    'https://cylc.github.io/cylc-doc/stable/html/workflow-design-guide/'
    'style-guide.html#'
)
URL_STUB = "https://cylc.github.io/cylc-doc/stable/html/7-to-8/"
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
        'url': STYLE_GUIDE + 'tab-characters',
        'index': 1
    },
    # Not a full test, but if a non section is not indented...
    re.compile(r'^[^\{\[|\s]'): {
        'short': 'Item not indented.',
        'url': STYLE_GUIDE + 'indentation',
        'index': 2
    },
    #            [section]
    re.compile(r'^\s+\[[^\[.]*\]'): {
        'short': 'Top level sections should not be indented.',
        'url': STYLE_GUIDE + 'indentation',
        'index': 3
    },
    # 2 or 4 space indentation both seem reasonable:
    re.compile(r'^(|\s|\s{2,3}|\s{5,})\[\[[^\[.]*\]\]'): {
        'short': (
            'Second level sections should be indented exactly '
            '4 spaces.'
        ),
        'url': STYLE_GUIDE + 'indentation',
        'index': 4
    },
    re.compile(r'^(|\s{1,7}|\s{9,})\[\[\[[^\[.]*\]\]\]'): {
        'short': (
            'Third level sections should be indented exactly '
            '8 spaces.'
        ),
        'url': STYLE_GUIDE + 'indentation',
        'index': 5
    },
    re.compile(r'\s$'): {
        'short': 'trailing whitespace.',
        'url': STYLE_GUIDE + 'trailing-whitespace',
        'index': 6
    },
    # Look for families in inherit= configurations.
    re.compile(
        r'''
          # match all inherit statements
          ^\s*inherit\s*=
          # filtering out those which match only valid family names
          (?!
            \s*
            # none, None and root are valid family names
            (none|None|root|
              (
                # as are families named with capital letters
                [A-Z0-9_-]+
                # which may include Cylc parameters
                | (<[^>]+>)
                # or Jinja2
                | ({[{%].*[%}]})
                # or EmPy
                | (@[\[{\(]).*([\]\}\)])
              )+
            )
            # this can be a comma separated list
            (
              \s*,\s*
              # none, None and root are valid family names
              (none|None|root|
                (
                  # as are families named with capital letters
                  [A-Z0-9_-]+
                  # which may include Cylc parameters
                  | (<[^>]+>)
                  # or Jinja2
                  | ({[{%].*[%}]})
                  # or EmPy
                  | (@[\[{\(]).*([\]\}\)])
                )+
              )
            )*
            # allow trailing commas and whitespace
            \s*,?\s*
            $
          )
        ''',
        re.X
    ): {
        'short': 'Family name contains lowercase characters.',
        'url': STYLE_GUIDE + 'task-naming-conventions',
        'index': 7
    },
    re.compile(r'{[{%]'): {
        'short': JINJA2_FOUND_WITHOUT_SHEBANG,
        'url': '',
        'index': 8
    },
    re.compile(r'platform\s*=\s*\$\(.*?\)'): {
        'short': 'Host Selection Script may be redundant with platform',
        'url': (
            'https://cylc.github.io/cylc-doc/stable/html/7-to-8/'
            'major-changes/platforms.html'
        ),
        'index': 9
    },
    re.compile(r'platform\s*=\s*(`.*?`)'): {
        'short': 'Using backticks to invoke subshell is deprecated',
        'url': 'https://github.com/cylc/cylc-flow/issues/3825',
        'index': 10
    },
    re.compile(r'(?<!{)#.*?{[{%]'): {
        'short': 'Cylc comments (#) do not prevent Jinja2 processing.',
        'url': '',
        'index': 11
    }
    # re.compile(r'^.{{maxlen},}'): {
    #     'short': 'line > {maxlen} characters.',
    #     'url': STYLE_GUIDE + 'line-length-and-continuation',
    #     'index': 8
    # },
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
    re.compile(r'host\s*=\s*(`.*?`)'): {
        'short': 'Using backticks to invoke subshell will fail at Cylc 8.',
        'url': 'https://github.com/cylc/cylc-flow/issues/3825'
    }
}
RULESETS = ['728', 'style', 'all']
EXTRA_TOML_VALIDATION = {
    'ignore': {
        lambda x: re.match(r'[A-Z]\d\d\d', x):
            '{item} not valid: Ignore codes should be in the form X001',
        lambda x: x in [
            f'{i["purpose"]}{i["index"]:03d}'
            for i in parse_checks(['728', 'style']).values()
        ]:
            '{item} is a not a known linter code.'
    },
    'rulesets': {
        lambda item: item in RULESETS:
            '{item} not valid: Rulesets can be '
            '\'728\', \'style\' or \'all\'.'
    },
    'max-line-length': {
        lambda x: isinstance(x, int):
            'max-line-length must be an integer.'
    },
    # consider checking that item is file?
    'exclude': {}
}


def validate_toml_items(tomldata):
    """Check that all tomldata items are lists of strings

    Explicitly checks and raises if tomldata not:
        - str in EXTRA_TOML_VALIDATION.keys()
        - item is not a list of strings.

    Plus additional validation for each set of values.
    """
    for key, items in tomldata.items():
        # Key should only be one of the allowed keys:
        if key not in EXTRA_TOML_VALIDATION.keys():
            raise CylcError(
                f'Only {[*EXTRA_TOML_VALIDATION.keys()]} '
                f'allowed as toml sections but you used {key}'
            )
        if key != 'max-line-length':
            # Item should be a list...
            if not isinstance(items, list):
                raise CylcError(
                    f'{key} should be a list, but was: {items}')
            # ... of strings
            for item in items:
                if not isinstance(item, str):
                    raise CylcError(
                        f'Config {item} should be a string but '
                        f'is {str(type(item))}'
                    )
                for check, message in EXTRA_TOML_VALIDATION[key].items():
                    if not check(item):
                        raise CylcError(
                            message.format(item=item)
                        )
    return True


def get_pyproject_toml(dir_):
    """if a pyproject.toml file is present open it and return settings.
    """
    keys = ['rulesets', 'ignore', 'exclude', 'max-line-length']
    tomlfile = Path(dir_ / 'pyproject.toml')
    tomldata = {}
    if tomlfile.is_file():
        try:
            loadeddata = tomli.loads(tomlfile.read_text())
        except tomli.TOMLDecodeError as exc:
            raise CylcError(f'pyproject.toml did not load: {exc}')

        if any(
            i in loadeddata for i in ['cylc-lint', 'cylclint', 'cylc_lint']
        ):
            for key in keys:
                tomldata[key] = loadeddata.get('cylc-lint').get(key, [])
            validate_toml_items(tomldata)
    if not tomldata:
        tomldata = {key: [] for key in keys}
    return tomldata


def merge_cli_with_tomldata(
    clidata, tomldata,
    override_cli_default_rules=False
):
    """Merge options set by pyproject.toml with CLI options.

    rulesets: CLI should override toml.
    ignore: CLI and toml should be combined with no duplicates.
    exclude: No CLI equivalent, return toml if any.

    Args:
        override_cli_default_rules: If user doesn't specifiy a ruleset use the
            rules from the tomlfile - i.e: if we've set 'rulesets': 'style'
            we probably don't want to get warnings about 728 upgrades by
            default, but only if we ask for it on the CLI.

    Examples:
    >>> result = merge_cli_with_tomldata(
    ... {'rulesets': ['foo'], 'ignore': ['R101'], 'exclude': []},
    ... {'rulesets': ['bar'], 'ignore': ['R100'], 'exclude': ['*.bk']})
    >>> result['ignore']
    ['R100', 'R101']
    >>> result['rulesets']
    ['foo']
    >>> result['exclude']
    ['*.bk']
    """
    if isinstance(clidata['rulesets'][0], list):
        clidata['rulesets'] = clidata['rulesets'][0]

    output = {}

    # Combine 'ignore' sections:
    output['ignore'] = sorted(set(clidata['ignore'] + tomldata['ignore']))

    # Replace 'rulesets from toml with those from CLI if they exist:

    if override_cli_default_rules:
        output['rulesets'] = (
            tomldata['rulesets'] if tomldata['rulesets']
            else clidata['rulesets']
        )
    else:
        output['rulesets'] = (
            clidata['rulesets'] if clidata['rulesets']
            else tomldata['rulesets']
        )

    # Return 'exclude' and 'max-line-length' for the tomldata:
    output['exclude'] = tomldata['exclude']
    output['max-line-length'] = tomldata.get('max-line-length', None)

    return output


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
                expr = rf'^\s*{name}\s*=\s*.*'
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


PURPOSE_FILTER_MAP = {
    'style': 'S',
    '728': 'U',
}


def parse_checks(check_args, ignores=None, max_line_len=None, reference=False):
    """Prepare dictionary of checks.

    Args:
        check_arg: list of types of checks to run,
            currently expecting '728' and/or 'style'
        ignores: list of codes to ignore.
        max_line_len: Adds a specific style warning for lines longer than
            this. (If None, rule not enforced)
        reference: Function is being used to get a reference. If true
            max-line-length will have a generic message, rather than
            using any specific value.
    """
    ignores = ignores or []
    parsedchecks = {}
    purpose_filters = [PURPOSE_FILTER_MAP[i] for i in check_args]

    checks = {'U': get_upgrader_info(), 'S': STYLE_CHECKS}

    for purpose, ruleset in checks.items():
        if purpose in purpose_filters:
            # Run through the rest of the config items.
            for index, (pattern, meta) in enumerate(ruleset.items(), start=1):
                meta.update({'purpose': purpose})
                if 'index' not in meta:
                    meta.update({'index': index})
                if f'{purpose}{index:03d}' not in ignores:
                    parsedchecks.update({pattern: meta})
            if 'S' in purpose and "S008" not in ignores:
                if not max_line_len:
                    max_line_len = 130
                regex = r"^.{" + str(max_line_len) + r"}"
                if reference:
                    msg = (
                        'line > ``<max_line_len>`` characters. Max line '
                        ' length set in pyproject.toml (default 130)'
                    )
                else:
                    msg = f'line > {max_line_len} characters.'
                parsedchecks[re.compile(regex)] = {
                    'short': msg,
                    'url': STYLE_GUIDE + 'line-length-and-continuation',
                    'index': 8,
                    'purpose': 'S'
                }
    return parsedchecks


def check_cylc_file(
    dir_, file_, checks,
    modify=False,
):
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

            if (
                check.findall(line)
                and (
                    not line.strip().startswith('#')
                    or message['index'] == 11  # commented-out Jinja2
                )
            ):
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


def get_cylc_files(
    base: Path, exclusions: Union[list, None] = None
) -> Generator[Path, None, None]:
    """Given a directory yield paths to check."""
    exclusions = [] if exclusions is None else exclusions
    except_these_files = [
        file for exclusion in exclusions for file in base.rglob(exclusion)]
    for rglob in FILEGLOBS:
        for path in base.rglob(rglob):
            # Exclude log directory:
            if (
                path.relative_to(base).parts[0] != 'log'
                and path not in except_these_files
            ):
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
        argdoc=[
            COP.optional(WORKFLOW_ID_OR_PATH_ARG_DOC)
        ],
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
        default='',
        choices=["728", "style", "all", ''],
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
    parser.add_option(
        '--ignore', '-n',
        help=(
            'Ignore this check number.'
        ),
        action='append',
        default=[],
        dest='ignores',
        metavar="CODE",
        choices=tuple([f'S{i["index"]:03d}' for i in STYLE_CHECKS.values()])
    )
    parser.add_option(
        '--exit-zero',
        help='Exit with status code "0" even if there are issues.',
        action='store_true',
        default=False,
        dest='exit_zero'
    )

    return parser


@cli_function(get_option_parser)
def main(parser: COP, options: 'Values', target=None) -> None:
    if options.ref_mode:
        if options.linter in {'all', ''}:
            rulesets = ['728', 'style']
        else:
            rulesets = [options.linter]
        print(get_reference_text(parse_checks(rulesets, reference=True)))
        sys.exit(0)

    # If target not given assume we are looking at PWD
    if target is None:
        target = str(Path.cwd())

    # make sure the target is a src/run directories
    _, _, target = parse_id(
        target,
        src=True,
        constraint='workflows',
    )

    # Get a list of checks bas ed on the checking options:
    # Allow us to check any number of folders at once
    count = 0
    target = target.parent
    ruleset_default = False
    if options.linter == 'all':
        options.linter = ['728', 'style']
    elif options.linter == '':
        options.linter = ['728', 'style']
        ruleset_default = True
    else:
        options.linter = [options.linter]
    tomlopts = get_pyproject_toml(target)
    mergedopts = merge_cli_with_tomldata(
        {
            'exclude': [],
            'ignore': options.ignores,
            'rulesets': options.linter
        },
        tomlopts,
        ruleset_default
    )

    # Check whether target is an upgraded Cylc 8 workflow.
    # If it isn't then we shouldn't run the 7-to-8 checks upon
    # it:
    cylc8 = (target / 'flow.cylc').exists()
    if not cylc8 and mergedopts['rulesets'] == ['728']:
        LOG.error(
            f'{target} not a Cylc 8 workflow: '
            'Lint after renaming '
            '"suite.rc" to "flow.cylc"'
        )
        # Exit with an error code if --exit-zero was not set.
        # Return codes: sys.exit(True) == 1, sys.exit(False) == 0
        sys.exit(not options.exit_zero)
    elif not cylc8 and '728' in mergedopts['rulesets']:
        check_names = mergedopts['rulesets']
        check_names.remove('728')
    else:
        check_names = mergedopts['rulesets']

    # Check each file:
    checks = parse_checks(
        check_names,
        ignores=mergedopts['ignore'],
        max_line_len=mergedopts['max-line-length']
    )
    for file_ in get_cylc_files(target, mergedopts['exclude']):
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
            f'Checked {target} against {check_names} '
            f'rules and found {count} issue'
            f'{"s" if count > 1 else ""}.'
        )
    else:
        msg = (
            f'{Fore.GREEN}'
            f'Checked {target} against {check_names} rules and '
            'found no issues.'
        )

    print(msg)

    # Exit with an error code if there were warnings and
    # if --exit-zero was not set.
    # Return codes: sys.exit(True) == 1, sys.exit(False) == 0
    sys.exit(count != 0 and not options.exit_zero)


# NOTE: use += so that this works with __import__
# (docstring needed for `cylc help all` output)
__doc__ += get_reference_rst(parse_checks(['728', 'style'], reference=True))
