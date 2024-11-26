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
# NOTE: docstring needed for `cylc help all` output and docs
# (if editing check this still comes out as expected)

COP_DOC = """cylc lint [OPTIONS] ARGS

Check .cylc and .rc files for code style, deprecated syntax and other issues.

By default, suggestions are written to stdout.

In-place mode ("-i, --inplace") writes suggestions into the file as comments.
Commit to version control before using this, in case you want to back out.

A non-zero return code will be returned if any issues are identified.
This can be overridden by providing the "--exit-zero" flag.
"""

NOQA = """
Individual errors can be ignored using the ``# noqa`` line comment.
It is good practice to specify specific errors you wish to ignore using
``# noqa: S002 S007 U999``
"""

TOMLDOC = """
pyproject.toml configuration:
   [tool.cylc.lint]
   ignore = ['S001', 'S002']    # List of rules to ignore
   exclude = ['etc/foo.cylc']   # List of files to ignore
   rulesets = ['style', '728']  # Sets default rulesets to check
   max-line-length = 130        # Max line length for linting
"""
import functools
import pkgutil
import re
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Counter as CounterType,
    Dict,
    Iterator,
    List,
    Optional,
    Union,
)

try:
    # BACK COMPAT: tomli
    #   Support for Python versions before tomllib was added to the
    #   standard library.
    # FROM: Python 3.7
    # TO: Python: 3.10
    from tomli import TOMLDecodeError, loads as toml_loads
except ImportError:
    from tomllib import (  # type: ignore[no-redef]
        loads as toml_loads,
        TOMLDecodeError,
    )

from ansimarkup import parse as cparse

import cylc.flow.flags
from cylc.flow import LOG, job_runner_handlers
from cylc.flow.cfgspec.workflow import SPEC, upg
from cylc.flow.exceptions import CylcError
from cylc.flow.id_cli import parse_id
from cylc.flow.job_runner_mgr import JobRunnerManager
from cylc.flow.loggingutil import set_timestamps
from cylc.flow.option_parsers import (
    WORKFLOW_ID_OR_PATH_ARG_DOC,
    CylcOptionParser as COP,
)
from cylc.flow.parsec.config import ParsecConfig
from cylc.flow.scripts.cylc import DEAD_ENDS
from cylc.flow.terminal import cli_function


if TYPE_CHECKING:
    from optparse import Values

    # BACK COMPAT: typing_extensions.Literal
    # FROM: Python 3.7
    # TO: Python 3.8
    from typing_extensions import Literal


LINT_TABLE = ['tool', 'cylc', 'lint']
LINT_SECTION = '.'.join(LINT_TABLE)

# BACK COMPAT: DEPR_LINT_SECTION
# url:
#     https://github.com/cylc/cylc-flow/issues/5811
# from:
#    8.1.0
# to:
#    8.3.0
# remove at:
#    8.4.0 ?
DEPR_LINT_SECTION = 'cylc-lint'

IGNORE = 'ignore'
EXCLUDE = 'exclude'
RULESETS = 'rulesets'
MAX_LINE_LENGTH = 'max-line-length'

DEPRECATED_ENV_VARS = {
    'CYLC_SUITE_HOST': 'CYLC_WORKFLOW_HOST',
    'CYLC_SUITE_OWNER': 'CYLC_WORKFLOW_OWNER',
    'CYLC_SUITE_SHARE_DIR': 'CYLC_WORKFLOW_SHARE_DIR',
    'CYLC_SUITE_SHARE_PATH': 'CYLC_WORKFLOW_SHARE_PATH',
    'CYLC_SUITE_NAME': 'CYLC_WORKFLOW_ID',
    'CYLC_SUITE_LOG_DIR': 'CYLC_WORKFLOW_LOG_DIR',
    'CYLC_SUITE_INITIAL_CYCLE_POINT': 'CYLC_WORKFLOW_INITIAL_CYCLE_POINT',
    'CYLC_SUITE_INITIAL_CYCLE_TIME': 'CYLC_WORKFLOW_INITIAL_CYCLE_TIME',
    'CYLC_SUITE_FINAL_CYCLE_POINT': 'CYLC_WORKFLOW_FINAL_CYCLE_POINT',
    'CYLC_SUITE_FINAL_CYCLE_TIME': 'CYLC_WORKFLOW_FINAL_CYCLE_TIME',
    'CYLC_SUITE_WORK_DIR': 'CYLC_WORKFLOW_WORK_DIR',
    'CYLC_SUITE_UUID': 'CYLC_WORKFLOW_UUID',
    'CYLC_SUITE_RUN_DIR': 'CYLC_WORKFLOW_RUN_DIR',
}

OBSOLETE_ENV_VARS = {
    'CYLC_SUITE_DEF_PATH',
    'CYLC_SUITE_DEF_PATH_ON_SUITE_HOST'
}


DEPRECATED_STRING_TEMPLATES = {
    'suite': ['workflow'],
    'suite_uuid': ['uuid'],
    'batch_sys_name': ['job_runner_name'],
    'batch_sys_job_id': ['job_id'],
    'user@host': ['platform_name'],
    'task_url': ['URL', '(if set in :cylc:conf:`[meta]URL`)'],
    'workflow_url': [
        'workflow_URL',
        '(if set in :cylc:conf:`[runtime][<namespace>][meta]URL`)',
    ],
}


LIST_ITEM = '\n    * '


deprecated_string_templates = {
    key: (
        re.compile(r'%\(' + key + r'\)s'),
        value
    )
    for key, value in DEPRECATED_STRING_TEMPLATES.items()
}


def get_wallclock_directives():
    """Get a set of directives equivalent to execution time limit"""
    job_runner_manager = JobRunnerManager()
    directives = {}
    for module in pkgutil.iter_modules(job_runner_handlers.__path__):
        directive = getattr(
            job_runner_manager._get_sys(module.name),
            'TIME_LIMIT_DIRECTIVE',
            None
        )
        if directive:
            directives[module.name] = directive
    return directives


WALLCLOCK_DIRECTIVES = get_wallclock_directives()


def check_wallclock_directives(line: str) -> Union[Dict[str, str], bool]:
    """Check for job runner specific directives
    equivalent to exection time limit.

    It's recommended that users prefer execution time limit
    because it gives the Cylc scheduler awareness should communications
    with a remote job runner be lost.

    Examples:
        >>> this = check_wallclock_directives
        >>> this('    -W 42:22')
        {'directive': '-W 42:22'}
    """
    for directive in set(WALLCLOCK_DIRECTIVES.values()):
        if line.strip().startswith(directive):
            return {'directive': line.strip()}
    return False


def check_jinja2_no_shebang(
    line: str,
    file: Path,
    function: Callable,
    jinja_shebang: bool = False,
    **kwargs
):
    """Check ONLY top level workflow files for jinja without shebangs.

    Examples:
        >>> func = re.compile(r'{{').findall

        >>> check_jinja2_no_shebang(
        ... '{{FOO}}',
        ... function=func, jinja_shebang=True, file=Path('foo.cylc'))
        False

        >>> check_jinja2_no_shebang(
        ... '{{FOO}}',
        ... function=func, jinja_shebang=False, file=Path('suite.rc'))
        ['{{']
    """
    if (
        jinja_shebang
        or file.name not in {'flow.cylc', 'suite.rc'}
    ):
        return False
    return function(line)


def check_if_jinja2(
    line: str,
    jinja_shebang: bool,
    function: Callable,
    **kwargs
):
    """Run function if Jinja2 switched on.

    Examples:
        >>> func = re.compile('foo').findall

        >>> check_if_jinja2('barfoo', jinja_shebang=False, function=func)
        False

        >>> check_if_jinja2('foofoo', jinja_shebang=True, function=func)
        ['foo', 'foo']

    """
    if jinja_shebang:
        return function(line)
    return False


def check_dead_ends(line: str) -> bool:
    """Check for dead end cylc scripts as defined in cylc.flow.scripts.cylc

    Examples:
        # Context:
        # [runtime]
        #   [[task]]
        #     script = \"\"\"

        >>> check_dead_ends('        cylc check-software')
        True

        >>> check_dead_ends('        cylc log')
        False
    """
    return any(
        f'cylc {dead_end}' in line for dead_end in DEAD_ENDS
    )


def check_for_suicide_triggers(
    line: str,
    file: Path,
    function: Callable,
    **kwargs
):
    """Check for suicide triggers, if file is a .cylc file.

    Examples:
        >>> func = lambda line: line

        # Suicide trigger in a *.cylc file:
        >>> check_for_suicide_triggers(
        ... 'x:fail => !y', function=func, file=Path('foo.cylc'))
        'x:fail => !y'

        # Suicide trigger in a suite.rc file:
        >>> check_for_suicide_triggers(
        ... 'x:fail => !y', function=func, file=Path('suite.rc'))
        False
    """
    if file.name.endswith('.cylc'):
        return function(line)
    return False


def check_for_deprecated_environment_variables(
    line: str
) -> Union[bool, dict]:
    """Warn that environment variables with SUITE in are deprecated

    Examples:
        >>> check_for_deprecated_environment_variables('CYLC_SUITE_HOST')
        {'vars': ['CYLC_SUITE_HOST: CYLC_WORKFLOW_HOST']}
    """
    vars_found = [
        f'{k}: {v}' for k, v in DEPRECATED_ENV_VARS.items()
        if k in line
    ]

    if len(vars_found) == 1:
        return {'vars': vars_found}
    elif vars_found:
        return {'vars': '\n * ' + '\n * '.join(vars_found)}
    return False


def check_for_obsolete_environment_variables(line: str) -> Dict[str, List]:
    """Warn that environment variables are obsolete.

    Examples:

        >>> this = check_for_obsolete_environment_variables
        >>> this('script = echo $CYLC_SUITE_DEF_PATH')
        {'vars': ['CYLC_SUITE_DEF_PATH']}
        >>> this('script = echo "irrelevent"')
        {}
    """
    vars_found = [i for i in OBSOLETE_ENV_VARS if i in line]
    if vars_found:
        return {'vars': vars_found}
    return {}


def check_for_deprecated_task_event_template_vars(
    line: str
) -> Optional[Dict[str, str]]:
    """Look for string variables which are no longer supported

    Examples:
        >>> this = check_for_deprecated_task_event_template_vars

        >>> this('hello = "My name is %(suite)s"')
        {'suggest': '\\n    * %(suite)s ⇒ %(workflow)s'}

        >>> this('x = %(user@host)s, %(suite)')
        {'suggest': '\\n    * %(user@host)s ⇒ %(platform_name)s'}

        >>> this('x = %(task_url)s')
        {'suggest': '\\n    * %(task_url)s ⇒ %(URL)s (if set in ...)'}
    """
    result = [
        f"%({key})s ⇒ %({replacement})s {' '.join(extra)}".rstrip()
        for key, (
            regex, (replacement, *extra),
        ) in deprecated_string_templates.items()
        if regex.findall(line)
    ]

    if result:
        return {'suggest': LIST_ITEM + LIST_ITEM.join(result)}
    return None


INDENTATION = re.compile(r'^(\s*)(.*)')


def check_indentation(line: str) -> bool:
    """The key value pair is not indented 4*X spaces

    n.b. We test for trailing whitespace and incorrect section indenting
    elsewhere

    Examples:

        >>> check_indentation('')
        False
        >>> check_indentation('   ')
        False
        >>> check_indentation('   [')
        False
        >>> check_indentation('baz')
        False
        >>> check_indentation('    qux')
        False
        >>> check_indentation('   foo')
        True
        >>> check_indentation('     bar')
        True
    """
    match = INDENTATION.findall(line)[0]
    if not match[0] or not match[1] or match[1].startswith('['):
        return False
    return bool(len(match[0]) % 4 != 0)


INHERIT_REGEX = re.compile(r'\s*inherit\s*=\s*(.*)')
FAM_NAME_IGNORE_REGEX = re.compile(
    # Stuff we want to ignore when checking for lowercase in family names
    r'''
        # comments
        (?<!{)\#.*
        # or Cylc parameters
        | <[^>]+>
        # or Jinja2
        | {{.*?}} | {%.*?%} | {\#.*?\#}
    ''',
    re.X
)
LOWERCASE_REGEX = re.compile(r'[a-z]')


def check_lowercase_family_names(line: str) -> bool:
    """Check for lowercase in family names.

    Examples:
        >>> check_lowercase_family_names(' inherit = FOO')
        False
        >>> check_lowercase_family_names(' inherit = foo')
        True
    """
    match = INHERIT_REGEX.match(line)
    if not match:
        return False
    # Replace stuff we want to ignore with a neutral char (tilde will do):
    content = FAM_NAME_IGNORE_REGEX.sub('~', match.group(1))
    return any(
        LOWERCASE_REGEX.search(i)
        for i in content.split(',')
        if i.strip(' \'"') not in {'None', 'none', 'root'}
    )


CHECK_FOR_OLD_VARS = re.compile(
    r'CYLC_VERSION\s*=\s*\{\{\s*CYLC_VERSION\s*\}\}'
    r'|ROSE_VERSION\s*=\s*\{\{\s*ROSE_VERSION\s*\}\}'
    r'|FCM_VERSION\s*=\s*\{\{\s*FCM_VERSION\s*\}\}'
)


def list_wrapper(line: str, check: Callable) -> Optional[Dict[str, str]]:
    """Take a line and a check function and return a Dict if there is a
    result, None otherwise.

    Returns

        Dict, in for {'vars': Error string}
    """
    result = check(line)
    if result:
        return {'vars': '\n    * '.join(result)}
    return None


FUNCTION = 'function'

STYLE_GUIDE = (
    'https://cylc.github.io/cylc-doc/stable/html/workflow-design-guide/'
    'style-guide.html#'
)
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
CHECKS_DESC = {
    'U': '7 to 8 upgrades',
    'A': 'Auto Generated 7 to 8 upgrades',
    'S': 'Style'
}
LINE_LEN_NO = 'S012'
# Checks Dictionary fields:
# TODO: Consider making the checks an object.
# Key: A unique reference number.
# - short: A short description of the issue.
# - url: A link to a fuller description.
# - function: A function to use to run the check.
# - kwargs: We want to pass a set of common kwargs to the check function.
# - evaluate commented lines: Run this check on commented lines.
# - rst: An rst description, for use in the Cylc docs.
STYLE_CHECKS = {
    "S001": {
        'short': 'Use multiple spaces, not tabs',
        'url': STYLE_GUIDE + 'tab-characters',
        FUNCTION: re.compile(r'^\t').findall
    },
    "S002": {
        'short': 'Item not indented.',
        # Non-indented items should be sections:
        'url': STYLE_GUIDE + 'indentation',
        FUNCTION: re.compile(r'^[^%\{\[|\s]').findall
    },
    "S003": {
        'short': 'Top level sections should not be indented.',
        'url': STYLE_GUIDE + 'indentation',
        FUNCTION: re.compile(r'^\s+\[[^\[.]*\]').findall
    },
    "S004": {
        'short': (
            'Second level sections should be indented exactly '
            '4 spaces.'
        ),
        'url': STYLE_GUIDE + 'indentation',
        FUNCTION: re.compile(r'^(|\s|\s{2,3}|\s{5,})\[\[[^\[.]*\]\]').findall
    },
    "S005": {
        'short': (
            'Third level sections should be indented exactly '
            '8 spaces.'
        ),
        'url': STYLE_GUIDE + 'indentation',
        FUNCTION: re.compile(r'^(|\s{1,7}|\s{9,})\[\[\[[^\[.]*\]\]\]').findall
    },
    "S006": {
        'short': 'trailing whitespace.',
        'url': STYLE_GUIDE + 'trailing-whitespace',
        FUNCTION: re.compile(r'[ \t]$').findall
    },
    "S007": {
        'short': 'Family name contains lowercase characters.',
        'url': STYLE_GUIDE + 'task-naming-conventions',
        FUNCTION: check_lowercase_family_names,
    },
    "S008": {
        'short': JINJA2_FOUND_WITHOUT_SHEBANG,
        'url': '',
        'kwargs': True,
        FUNCTION: functools.partial(
            check_jinja2_no_shebang,
            function=re.compile(r'{[{%]').findall
        )
    },
    "S009": {
        'short': 'Host Selection Script may be redundant with platform',
        'url': (
            'https://cylc.github.io/cylc-doc/stable/html/7-to-8/'
            'major-changes/platforms.html'
        ),
        FUNCTION: re.compile(r'platform\s*=\s*\$\(.*?\)').findall,
    },
    "S010": {
        'short': 'Using backticks to invoke subshell is deprecated',
        'url': 'https://github.com/cylc/cylc-flow/issues/3825',
        FUNCTION: re.compile(r'platform\s*=\s*(`.*?`)').findall,
    },
    "S011": {
        'short': 'Cylc will process commented Jinja2!',
        'url': '',
        'kwargs': True,
        'evaluate commented lines': True,
        FUNCTION: functools.partial(
            check_if_jinja2,
            function=re.compile(r'(?<!{)#[^$].*?{[{%]').findall
        )
    },
    'S012': {
        'short': 'This number is reserved for line length checks',
    },
    'S013': {
        'short': 'Items should be indented in 4 space blocks.',
        FUNCTION: check_indentation
    },
    'S014': {
        'short': (
            'Use ``[runtime][TASK]execution time limit``'
            ' rather than job runner directive: ``{directive}``.'
        ),
        'rst': (
            "Use :cylc:conf:`flow.cylc[runtime][<namespace>]execution "
            "time limit` rather than directly specifying a timeout "
            "directive, otherwise Cylc has no way of knowing when the job "
            "should have finished. Cylc automatically translates the "
            "execution time limit to the correct timeout directive for the "
            "particular job runner:\n"
        )
        + ''.join((
            f'\n * ``{directive}`` ({job_runner})'
            for job_runner, directive in WALLCLOCK_DIRECTIVES.items()
        )),
        FUNCTION: check_wallclock_directives,
    },
    'S015': {
        'short': (
            '`=>` implies line continuation without `\\`.'
        ),
        FUNCTION: re.compile(r'=>\s*\\').findall
    },
}
# Subset of deprecations which are tricky (impossible?) to scrape from the
# upgrader.
MANUAL_DEPRECATIONS = {
    "U001": {
        'short': (
            DEPENDENCY_SECTION_MSG['text'] + ' (``[dependencies]`` detected)'
        ),
        'url': '',
        'rst': (
            DEPENDENCY_SECTION_MSG['rst'] + ' (``[dependencies]`` detected)'
        ),
        FUNCTION: re.compile(SECTION2.format('dependencies')).findall,
    },
    "U002": {
        'short': DEPENDENCY_SECTION_MSG['text'] + ' (``graph =`` detected)',
        'url': '',
        'rst': DEPENDENCY_SECTION_MSG['rst'] + ' (``graph =`` detected)',
        FUNCTION: re.compile(r'graph\s*=\s*').findall,
    },
    "U003": {
        'short': JOBANDREMOTE_SECTION_MSG['text'].format('remote'),
        'url': '',
        'rst': JOBANDREMOTE_SECTION_MSG['rst'].format('remote'),
        FUNCTION: re.compile(SECTION3.format('remote')).findall
    },
    "U004": {
        'short': JOBANDREMOTE_SECTION_MSG['text'].format('job'),
        'url': '',
        'rst': JOBANDREMOTE_SECTION_MSG['rst'].format('job'),
        FUNCTION: re.compile(SECTION3.format('job')).findall,
    },
    "U005": {
        'short': (
            'flow.cylc[runtime][<namespace>][job]batch system -> '
            'global.cylc[platforms][<platform name>]job runner'
        ),
        'url': '',
        'rst': (
            '``flow.cylc[runtime][<namespace>][job]batch system`` -> '
            '``global.cylc[platforms][<platform name>]job runner``'
        ),
        FUNCTION: re.compile(r'batch system\s*=\s*').findall,
    },
    "U006": {
        'short': 'Using backticks to invoke subshell will fail at Cylc 8.',
        'url': 'https://github.com/cylc/cylc-flow/issues/3825',
        FUNCTION: re.compile(r'host\s*=\s*(`.*?`)').findall,
    },
    'U007': {
        'short': (
            'Use built in platform selection instead of rose host-select.'),
        'url': (
            'https://cylc.github.io/cylc-doc/stable/html/7-to-8/'
            'major-changes/platforms.html'),
        FUNCTION: re.compile(r'platform\s*=\s*\$\(\s*rose host-select').findall
    },
    'U008': {
        'short': 'Suicide triggers are not required at Cylc 8.',
        'url': (
            'https://cylc.github.io/cylc-doc/stable/html/7-to-8'
            '/major-changes/suicide-triggers.html'),
        'kwargs': True,
        FUNCTION: functools.partial(
            check_for_suicide_triggers,
            function=re.compile(r'=>\s*\!.*').findall
        ),
    },
    'U009': {
        'short': 'This line contains an obsolete Cylc CLI command.',
        'url': '',
        FUNCTION: check_dead_ends
    },
    'U010': {
        'short': 'rose suite-hook is deprecated at Rose 2,',
        'url': '',
        FUNCTION: lambda line: 'rose suite-hook' in line,
    },
    'U011': {
        'short': 'Leading zeros are no longer valid for Jinja2 integers.',
        'url': (
            'https://cylc.github.io/cylc-doc/stable/html/7-to-8/major-changes'
            '/python-2-3.html#jinja2-integers-with-leading-zeros'),
        'kwargs': True,
        FUNCTION: functools.partial(
            check_if_jinja2,
            function=re.compile(r'\{%\s*set\s*.+?\s*=\s*0\d+\s*%\}').findall
        )
    },
    'U012': {
        'short': (
            'Deprecated environment variables: {vars}'),
        'rst': (
            'The following environment variables are deprecated:\n\n'
            '.. list-table::'
            '\n   :header-rows: 1'
            '\n\n   * - Deprecated Variable'
            '\n     - New Variable'
        ) + ''.join(
            [
                f'\n   * - ``{old}``\n     - ``{new}``'
                for old, new in DEPRECATED_ENV_VARS.items()
            ]
        ),
        'url': (
            'https://cylc.github.io/cylc-doc/stable/html/reference/'
            'job-script-vars/index.html'
        ),
        FUNCTION: check_for_deprecated_environment_variables,
    },
    'U013': {
        'short': (
            'Obsolete environment variables: {vars}'),
        'rst': (
            'The following environment variables are obsolete:\n\n'
            + ''.join([f'\n * ``{old}``' for old in OBSOLETE_ENV_VARS])
        ),
        'url': (
            'https://cylc.github.io/cylc-doc/stable/html/reference/'
            'job-script-vars/index.html'
        ),
        FUNCTION: check_for_obsolete_environment_variables,
    },
    'U014': {
        'short': 'Use "isodatetime [ref]" instead of "rose date [-c]"',
        'rst': (
            'For datetime operations in task scripts:\n\n'
            ' * Use ``isodatetime`` instead of ``rose date``\n'
            ' * Use ``isodatetime ref`` instead of ``rose date -c`` for '
            'the current cycle point\n'
        ),
        'url': (
            'https://cylc.github.io/cylc-doc/stable/html/7-to-8/'
            'cheat-sheet.html#datetime-operations'
        ),
        FUNCTION: re.compile(r'rose +date').findall,
    },
    'U015': {
        'short': (
            'Deprecated template variables: {suggest}'),
        'rst': (
            "The following deprecated template variables, mostly used in "
            "event handlers, should be replaced:\n"
            + ''.join(
                f"\n * ``{old}`` ⇒ ``{new}`` {' '.join(extra)}".rstrip()
                for old, (new, *extra) in DEPRECATED_STRING_TEMPLATES.items()
            )
        ),
        'url': (
            'https://cylc.github.io/cylc-doc/stable/html/user-guide/'
            'writing-workflows/runtime.html#task-event-template-variables'
        ),
        FUNCTION: check_for_deprecated_task_event_template_vars,
    },
    'U016': {
        'short': 'Deprecated template vars: {vars}',
        'rst': (
            'It is no longer necessary to configure the environment variables '
            '``CYLC_VERSION``, ``ROSE_VERSION`` or ``FCM_VERSION``.'
        ),
        'url': (
            'https://cylc.github.io/cylc-doc/stable/html/plugins/'
            'cylc-rose.html#special-variables'
        ),
        FUNCTION: functools.partial(
            list_wrapper, check=CHECK_FOR_OLD_VARS.findall),
    },
    'U017': {
        'short': (
            '`&` and `|` imply line continuation without `\\`'
        ),
        FUNCTION: re.compile(r'[&|]\s*\\').findall
    },
}
ALL_RULESETS = ['728', 'style', 'all']
EXTRA_TOML_VALIDATION = {
    IGNORE: {
        lambda x: re.match(r'[A-Z]\d\d\d', x):
            '{item} not valid: Ignore codes should be in the form X001',
        lambda x: x in parse_checks(['728', 'style']):
            '{item} is a not a known linter code.'
    },
    RULESETS: {
        lambda item: item in ALL_RULESETS:
            '{item} not valid: Rulesets can be '
            '\'728\', \'style\' or \'all\'.'
    },
    MAX_LINE_LENGTH: {
        lambda x: isinstance(x, int):
            'max-line-length must be an integer.'
    },
    # consider checking that item is file?
    EXCLUDE: {}
}


def parse_ruleset_option(ruleset: str) -> List[str]:
    if ruleset in {'all', ''}:
        return ['728', 'style']
    return [ruleset]


def get_url(check_meta: Dict) -> str:
    """Get URL from check data.

    If the URL doesn't start with http then prepend with address
    of the 7-to-8 upgrade guide.

    Examples:
        >>> get_url({'no': 'url key'})
        ''
        >>> get_url({'url': ''})
        ''
        >>> get_url({'url': 'https://www.h2g2.com/'})
        'https://www.h2g2.com/'
        >>> get_url({'url': 'cheat-sheet.html'})
        'https://cylc.github.io/cylc-doc/stable/html/7-to-8/cheat-sheet.html'
    """
    url = check_meta.get('url', '')
    if url and not url.startswith('http'):
        url = (
            "https://cylc.github.io/cylc-doc/stable/html/7-to-8/"
            + check_meta['url']
        )
    return url


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
                f'allowed as toml sections but you used "{key}"'
            )
        if key != MAX_LINE_LENGTH:
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


def get_pyproject_toml(dir_: Path) -> Dict[str, Any]:
    """if a pyproject.toml file is present open it and return settings.
    """
    tomlfile = dir_ / 'pyproject.toml'
    tomldata: Dict[str, Union[List[str], int, None]] = {
        RULESETS: [],
        IGNORE: [],
        EXCLUDE: [],
        MAX_LINE_LENGTH: None,
    }
    if tomlfile.is_file():
        try:
            loadeddata = toml_loads(tomlfile.read_text())
        except TOMLDecodeError as exc:
            raise CylcError(f'pyproject.toml did not load: {exc}') from None

        _tool, _cylc, _lint = LINT_TABLE
        try:
            data = loadeddata[_tool][_cylc][_lint]
        except KeyError:
            if DEPR_LINT_SECTION in loadeddata:
                LOG.warning(
                    f"The [{DEPR_LINT_SECTION}] section in pyproject.toml is "
                    f"deprecated. Use [{LINT_SECTION}] instead."
                )
            data = loadeddata.get(DEPR_LINT_SECTION, {})
        tomldata.update(data)
        validate_toml_items(tomldata)

    return tomldata


def merge_cli_with_tomldata(target: Path, options: 'Values') -> Dict[str, Any]:
    """Get a list of checks based on the checking options

    Args:
        target: Location being linted, in which we might find a
            pyproject.toml file.
        options: Cli Options

    This has not been merged with merged with the logic in
    _merge_cli_with_tomldata to keep the testing of file-system touching
    and pure logic separate.
    """
    ruleset_default = (options.ruleset == '')
    options.ruleset = parse_ruleset_option(options.ruleset)
    tomlopts = get_pyproject_toml(target)
    return _merge_cli_with_tomldata(
        {
            EXCLUDE: [],
            IGNORE: options.ignores,
            RULESETS: options.ruleset
        },
        tomlopts,
        ruleset_default
    )


def _merge_cli_with_tomldata(
    clidata: Dict[str, Any],
    tomldata: Dict[str, Any],
    override_cli_default_rules: bool = False
) -> Dict[str, Any]:
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
    >>> result = _merge_cli_with_tomldata(
    ... {'rulesets': ['foo'], 'ignore': ['R101'], 'exclude': []},
    ... {'rulesets': ['bar'], 'ignore': ['R100'], 'exclude': ['*.bk']})
    >>> result['ignore']
    ['R100', 'R101']
    >>> result['rulesets']
    ['foo']
    >>> result['exclude']
    ['*.bk']
    """
    if isinstance(clidata[RULESETS][0], list):
        clidata[RULESETS] = clidata[RULESETS][0]

    output = {}

    # Combine 'ignore' sections:
    output[IGNORE] = sorted(set(clidata[IGNORE] + tomldata[IGNORE]))

    # Replace 'rulesets' from toml with those from CLI if they exist:

    if override_cli_default_rules:
        output[RULESETS] = (
            tomldata[RULESETS] if tomldata[RULESETS]
            else clidata[RULESETS]
        )
    else:
        output[RULESETS] = (
            clidata[RULESETS] if clidata[RULESETS]
            else tomldata[RULESETS]
        )

    # Return 'exclude' and 'max-line-length' for the tomldata:
    output[EXCLUDE] = tomldata[EXCLUDE]
    output[MAX_LINE_LENGTH] = tomldata.get(MAX_LINE_LENGTH, None)

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

    for upgrades_for_version in upgrades.values():
        for index, upgrade in enumerate(upgrades_for_version):
            # Set a flag indicating that a variable has been moved.
            is_dep, is_obs = False, False
            if upgrade['new'] is None:
                section_name = list_to_config(
                    upgrade["old"], upgrade["is_section"])
                short = f'{section_name} - not available at Cylc 8'
                rst = f'``{section_name}`` is not available at Cylc 8'
                is_obs = True
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
                is_dep = True

            # Check whether upgrade is section:
            if upgrade['is_section'] is True:
                section_depth = len(upgrade['old'])
                start = r'\[' * section_depth
                end = r'\]' * section_depth
                name = upgrade["old"][-1]
                expr = fr'{start}\s*{name}\s*{end}\s*$'
            else:
                name = upgrade["old"][-1]
                expr = rf'^\s*{name}\s*=\s*.*'

            deprecations[f'A{index:03d}'] = {
                'short': short,
                'url': '',
                'rst': rst,
                FUNCTION: re.compile(expr).findall,
                'is_obs': is_obs,
                'is_dep': is_dep,
            }

    return deprecations


PURPOSE_FILTER_MAP = {
    'style': 'S',
    '728': 'UA',
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
    purpose_filters = [
        purpose
        for arg in check_args
        for purpose in PURPOSE_FILTER_MAP[arg]
    ]

    checks = {
        'S': STYLE_CHECKS,
        'U': MANUAL_DEPRECATIONS,
        'A': get_upgrader_info(),
    }
    for purpose, ruleset in checks.items():
        if purpose in purpose_filters:
            # Run through the rest of the config items.
            for index, meta in ruleset.items():
                meta.update({'purpose': purpose})
                if f'{index}' not in ignores:
                    parsedchecks.update({index: meta})
            if 'S' in purpose and LINE_LEN_NO not in ignores:
                # Special handling for max line length:
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
                parsedchecks[LINE_LEN_NO] = {
                    'short': msg,
                    'url': STYLE_GUIDE + 'line-length-and-continuation',
                    FUNCTION: re.compile(regex).findall,
                    'purpose': 'S'
                }
    return parsedchecks


def get_index_str(meta: dict, index: str) -> str:
    """Printable purpose string - mask useless numbers for auto-generated
    upgrades."""
    if meta.get('is_dep', None):
        return 'U998'
    elif meta.get('is_obs', None):
        return 'U999'
    else:
        return f'{index}'


def check_cylc_file(
    file: Path,
    file_rel: Path,
    checks: Dict[str, dict],
    counter: CounterType[str],
    modify: bool = False,
):
    """Check A Cylc File for Cylc 7 Config"""
    with open(file, 'r') as cylc_file:
        # generator which reads and lints one line at a time
        linter = lint(
            file_rel,
            cylc_file,
            checks,
            counter,
            modify,
        )

        if modify:
            # write modifications into a ".temp" file
            modify_file_path = file.parent / f'{file.name}.temp'
            with open(modify_file_path, 'w+') as modify_file:
                for line in linter:
                    modify_file.write(line)
            # replace the original with the ".temp" file
            shutil.move(str(modify_file_path), file)
        else:
            for _line in linter:
                pass


def no_qa(line: str, index: str):
    """This line has a no-qa comment.

    Examples:
        # No comment, no exception:
        >>> no_qa('foo = bar', 'S001')
        False

        # Comment, no error codes, no checking:
        >>> no_qa('foo = bar # noqa', 'S001')
        True

        # Comment, no relevent error codes, no checking:
        >>> no_qa('foo = bar # noqa: S999, 997', 'S001')
        False

        # Comment, relevent error codes, checking:
        >>> no_qa('foo = bar # noqa: S001 S003', 'S001')
        True
    """
    NOQA = re.compile(r'.*#\s*[Nn][Oo][Qq][Aa]:?(.*)')
    noqa = NOQA.findall(line)
    if noqa and (noqa[0] == '' or index in noqa[0]):
        return True
    return False


def lint(
    file_rel: Path,
    lines: Iterator[str],
    checks: Dict[str, dict],
    counter: CounterType[str],
    modify: bool = False,
    write: Callable = print
) -> Iterator[str]:
    """Lint text, one line at a time.

    Arguments:
        file_rel:
            The filepath relative to the workflow configuration directory
            (used in messages).
        lines:
            Iterator which produces one line of text at a time
            e.g. open(file) or iter(['foo\n', 'bar\n', 'baz\n'].
        counter:
            Counter for counting lint hits per category.
        modify:
            If True, this generator will yield the file one line at a time
            with comments inserted to help users fix their lint.
        write:
            A function for reporting lint messages.

    Yields:
        The original file with added comments when `modify is True`.

    """
    # get the first line
    line_no = 1
    line = next(lines)
    # check if it is a jinja2 shebang
    jinja_shebang = line.strip().lower() == JINJA2_SHEBANG

    while True:
        # run lint checks against the current line
        for index, check_meta in checks.items():
            # Skip commented line unless check says not to.
            index_str = get_index_str(check_meta, index)
            if (
                (
                    line.strip().startswith('#')
                    and not check_meta.get('evaluate commented lines', False)
                )
                or no_qa(line, index_str)
            ):
                continue

            if check_meta.get('kwargs', False):
                # Use a more complex function with keywords:
                check_function = functools.partial(
                    check_meta['function'],
                    check_meta=check_meta,
                    file=file_rel,
                    jinja_shebang=jinja_shebang,
                )
            else:
                # Just going to pass the line to the check function:
                check_function = check_meta['function']

            # Run the check:
            check = check_function(line)

            if check:
                # we have lint!
                if isinstance(check, dict):
                    msg = check_meta['short'].format(**check)
                else:
                    msg = check_meta['short']
                counter[check_meta['purpose']] += 1
                if modify:
                    # insert a command to help the user
                    url = get_url(check_meta)

                    yield (
                        f'# [{index_str}]: '
                        f'{msg}\n'
                        f'# - see {url}\n'
                    )
                else:
                    # write a message to inform the user
                    write(cparse(
                        '<yellow>'
                        f'[{index_str}] {file_rel}:{line_no}: {msg}'
                        '</yellow>'
                    ))
        if modify:
            yield line

        try:
            # get the next line
            line = next(lines)
        except StopIteration:
            # end of interator
            return
        line_no += 1


def get_cylc_files(
    base: Path, exclusions: Union[list, None] = None
) -> Iterator[Path]:
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


def get_reference(ruleset: str, output_type: 'Literal["text", "rst"]') -> str:
    """Fill out a template with all the issues Cylc Lint looks for.
    """
    checks = parse_checks(
        parse_ruleset_option(ruleset),
        reference=True
    )

    issue_heading_template = (
        '\n{url}_\n{underline}\n{summary}\n\n' if output_type == 'rst' else
        '\n{check}:\n    {summary}\n    {url}\n\n'
    )
    output = ''
    current_checkset = ''
    for index, meta in checks.items():
        # Check if the purpose has changed - if so create a new
        # section heading:
        if meta['purpose'] != current_checkset:
            current_checkset = meta['purpose']
            title = CHECKS_DESC[meta["purpose"]]
            output += '\n{title}\n{underline}\n'.format(
                title=title, underline="-" * len(title)
            )

            if current_checkset == 'A':
                output += (
                    'U998 and U999 represent automatically generated'
                    ' sets of deprecations and upgrades.'
                )

        # Fill a template with info about the issue.
        if output_type == 'rst':
            summary = meta.get("rst", meta['short'])
        elif output_type == 'text':
            summary = meta.get("short").replace('``', '')

        if current_checkset == 'A':
            # Condensed check summary for auto-generated lint items.
            if output_type == 'rst':
                output += '\n'
            output += '\n* ' + summary
        else:
            check = get_index_str(meta, index)
            template = issue_heading_template
            url = get_url(meta)
            if output_type == 'rst':
                url = f'`{check} <{url}>`' if url else f'{check}'
            msg = template.format(
                title=index,
                check=check,
                summary=summary,
                url=url,
                underline=(len(url) + 1) * '^'
            )
            output += msg
    output += '\n'
    return output


def target_version_check(
    target: Path,
    quiet: 'Values',
    mergedopts: Dict[str, Any]
) -> List:
    """
    Check whether target is an upgraded Cylc 8 workflow.

    If it isn't then we shouldn't run the 7-to-8 checks upon
    it.

    If it isn't and the only ruleset requested by the user is '728'
    we should exit with an error code unless the user has specifically
    disabled thatr with --exit-zero.
    """
    cylc8 = (target / 'flow.cylc').exists()
    if not cylc8 and mergedopts[RULESETS] == ['728']:
        LOG.error(
            f'{target} not a Cylc 8 workflow: '
            'Lint after renaming '
            '"suite.rc" to "flow.cylc"'
        )
        sys.exit(not quiet)
    elif not cylc8 and '728' in mergedopts[RULESETS]:
        check_names = mergedopts[RULESETS]
        check_names.remove('728')
    else:
        check_names = mergedopts[RULESETS]
    return check_names


def get_option_parser() -> COP:
    parser = COP(
        (
            COP_DOC
            + NOQA.replace('``', '"')
            + TOMLDOC
        ),
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
        dest='ruleset'
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
        choices=list(STYLE_CHECKS.keys()) + [LINE_LEN_NO]
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
    if cylc.flow.flags.verbosity < 2:
        set_timestamps(LOG, False)

    if options.ref_mode:
        print(get_reference(options.ruleset, 'text'))
        sys.exit(0)

    # If target not given assume we are looking at PWD:
    if target is None:
        target = str(Path.cwd())

    # make sure the target is a src/run directory:
    _, _, target = parse_id(
        target,
        src=True,
        constraint='workflows',
    )

    # We want target to be the containing folder, not the flow.cylc
    # file identified by parse_id:
    target = target.parent

    mergedopts = merge_cli_with_tomldata(target, options)

    check_names = target_version_check(
        target=target, quiet=options.exit_zero, mergedopts=mergedopts)

    # Get the checks object.
    checks = parse_checks(
        check_names,
        ignores=mergedopts[IGNORE],
        max_line_len=mergedopts[MAX_LINE_LENGTH]
    )

    # Check each file matching a pattern:
    counter: CounterType[str] = Counter()
    for file in get_cylc_files(target, mergedopts[EXCLUDE]):
        LOG.debug(f'Checking {file}')
        check_cylc_file(
            file,
            file.relative_to(target),
            checks,
            counter,
            options.inplace,
        )

    if counter:
        total_lint_hits = sum(counter.values())
        msg = cparse(
            '\n<yellow>'
            f'Checked {target} against {check_names} '
            f'rules and found {total_lint_hits} issue'
            f'{"s" if total_lint_hits > 1 else ""}.'
            '</yellow>'
        )
    else:
        msg = cparse(
            '<green>'
            f'Checked {target} against {check_names} rules and '
            'found no issues.'
            '</green>'
        )

    print(msg)

    # Exit with an error code if there were warnings and
    # if --exit-zero was not set.
    # Return codes: sys.exit(True) == 1, sys.exit(False) == 0
    sys.exit(bool(counter) and not options.exit_zero)


# NOTE: use += so that this works with __import__
# (docstring needed for `cylc help all` output)
__doc__ += NOQA
__doc__ += get_reference('all', 'rst')
