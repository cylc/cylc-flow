#!/usr/bin/env python3
# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Tests `cylc lint` CLI Utility."""

from collections import Counter
import logging
from pathlib import Path
from pprint import pformat
import re
from textwrap import dedent
from types import SimpleNamespace

import pytest
from pytest import param

from cylc.flow.scripts.lint import (
    LINT_SECTION,
    MANUAL_DEPRECATIONS,
    check_lowercase_family_names,
    get_cylc_files,
    get_pyproject_toml,
    get_reference,
    get_upgrader_info,
    lint,
    _merge_cli_with_tomldata,
    parse_checks,
    validate_toml_items
)
from cylc.flow.exceptions import CylcError

STYLE_CHECKS = parse_checks(['style'])
UPG_CHECKS = parse_checks(['728'])

TEST_FILE = '''
[visualization]

[cylc]
    include at start-up = foo
    exclude at start-up = bar
    reset timer = false
    log resolved dependencies = True
    required run mode = False
    health check interval = PT10M
    abort if any task fails = true
    suite definition directory = '/woo'
    disable automatic shutdown = false
    spawn to max active cycle points = false
    [[reference test]]
        allow task failures = true
    [[simulation]]
        disable suite event handlers = true
    [[authentication]]
    [[environment]]
    force run mode = dummy
    [[events]]
        reset inactivity timer = 42
        abort on stalled = True
        abort on timeout = False
        abort if startup handler fails= True  # deliberately not added a space.
        abort if shutdown handler fails= True
        abort if timeout handler fails = True
        abort if stalled handler fails = True
        abort if inactivity handler fails = False
        aborted handler = woo
        stalled handler = bar
        timeout handler = bas
        shutdown handler = qux
        startup handler = now
        inactivity handler = bored
        mail to = eleanor.rigby@beatles.lv
        mail from = fr.mckenzie@beatles.lv
        mail footer = "Collecting The Rice"
        mail smtp = 123.456.789.10
        timeout = 30
        inactivity = 30
        abort on inactivity = 30
    [[parameters]]
    [[parameter templates]]
    [[mail]]
        task event mail interval    = PT4M # deliberately added lots of spaces.

[scheduling]
    max active cycle points = 5
    hold after point = 20220101T0000Z
    [[dependencies]]
        [[[R1]]]
            graph = """
                MyFaM:finish-all => remote => !mash_theme
                a & \\
                b => c
                c | \\
                d => e
            """

[runtime]
    [[root]]
        [[[environment]]]
            CYLC_VERSION={{CYLC_VERSION}}
            ROSE_VERSION  = {{ROSE_VERSION     }}
            FCM_VERSION = {{   FCM_VERSION   }}

    [[MyFaM]]
        extra log files = True
        {% from 'cylc.flow' import LOG %}
        pre-script = "echo ${CYLC_SUITE_DEF_PATH}"
        script = {{HELLOWORLD}}
        post-script = "echo ${CYLC_SUITE_INITIAL_CYCLE_TIME}"
        env-script = POINT=$(rose  date 2059 --offset P1M)
        [[[suite state polling]]]
            template = and
        [[[remote]]]
            host = parasite
            suite definition directory = '/home/bar'
        [[[job]]]
            batch system = slurm
            shell = fish
        [[[events]]]
            mail retry delays = PT30S
            warning handler = frr.sh
            submission timeout handler = faiuhdf
            submission retry handler = vhbayhrbfgau
            submission failed handler = giaSEHFUIHJ
            failed handler = woo
            execution timeout handler = sdfghjkl
            expired handler = %(suite_uuid)s %(user@host)s
            late handler = dafuhj
            submitted handler = dafuhj
            started handler = dafuhj
            succeeded handler = dafuhj
            custom handler = efrgh
            critical handler = fgjdsfs
            retry handler = dfaiuhfrgpa
            sumbission handler = fas9hrfgaiuph

# Shouldn't object to a comment, unlike the terrible indents below:
   [[bad indent]]
        inherit = MyFaM

     [[remote]]
        platform = $(rose host-select parasite)
        script = "cylc nudge"
        post-script = "rose suite-hook"

 [meta]
    [[and_another_thing]]
        [[[remote]]]
            host = `rose host-select thingy`

%include foo.cylc
'''


LINT_TEST_FILE = '''
\t[scheduler]

 [scheduler]

[[dependencies]]
{% set   N = 009 %}
{% foo %}
{{foo}}
# {{quix}}
    R1 = """
        foo & \\
        bar => \\
        baz
    """

[runtime]
    [[this_is_ok]]
      script = echo "this is incorrectly indented"

          [[foo]]
        inherit = hello
     [[[job]]]
something\t
    [[bar]]
        platform = $(some-script foo)
            [[[directives]]]
                -l walltime = 666
    [[baz]]
        run mode = skip
        platform = `no backticks`
        [[[skip]]]
            outputs = succeeded, failed
''' + (
    '\nscript = the quick brown fox jumps over the lazy dog until it becomes '
    'clear that this line is longer than the default 130 character limit.'
)


def lint_text(text, checks, ignores=None, modify=False):
    checks = parse_checks(checks, ignores)
    counter = Counter()
    messages = []
    outlines = list(
        lint(
            Path('flow.cylc'),
            iter(text.splitlines()),
            checks,
            counter,
            modify=modify,
            write=messages.append,
        )
    )

    return SimpleNamespace(
        counter=counter,
        messages=messages,
        outlines=outlines
    )


def filter_strings(items, contains):
    """Return only items which contain a given string."""
    return [
        message
        for message in items
        if contains in message
    ]


def assert_contains(items, contains, instances=None):
    """Pass if at least one item contains a given string."""
    filtered = filter_strings(items, contains)
    if not filtered:
        raise Exception(
            f'Could not find: "{contains}" in:\n'
            + pformat(items))
    elif instances and len(filtered) != instances:
        raise Exception(
            f'Expected "{contains}" to appear {instances} times'
            f', got it {len(filtered)} times.')


EXPECT_INSTANCES_OF_ERR = {
    16: 3,
}


@pytest.mark.parametrize(
    # 11 won't be tested because there is no jinja2 shebang
    'number', set(range(1, len(MANUAL_DEPRECATIONS) + 1)) - {11}
)
def test_check_cylc_file_7to8(number):
    """TEST File has one of each manual deprecation;"""
    lint = lint_text(TEST_FILE, ['728'])
    instances = EXPECT_INSTANCES_OF_ERR.get(number, None)
    # U0008 Has been removed, but we don't want to change the numbering
    if number != 8:
        assert_contains(lint.messages, f'[U{number:03d}]', instances)


def test_check_cylc_file_7to8_has_shebang():
    """Jinja2 code comments will not be added if shebang present"""
    lint = lint_text('#!jinja2\n{{FOO}}', '', '[scheduler]')
    assert not lint.counter


def test_check_cylc_file_line_no():
    """It prints the correct line numbers"""
    lint = lint_text(TEST_FILE, ['728'])
    # the first message should be for line number 2 (line is a shebang)
    assert ':2:' in lint.messages[0]


@pytest.mark.parametrize(
    'line',
    [
        # lowercase family names are not permitted
        'inherit = g',
        'inherit = FOO, bar',
        'inherit = None, bar',
        'inherit = A, b, C',
        'inherit = "A", "b"',
        "inherit = 'A', 'b'",
        'inherit = FOO_BAr',
        # whitespace & trailing commas
        '  inherit  =  a  ,  ',
        # parameters, templating code should be ignored
        # but any lowercase chars before or after should not
        'inherit = A<x>z',
        'inherit = A{{ x }}z',
        'inherit = N{# #}one',
        'inherit = A@( x )z',
    ]
)
def test_check_lowercase_family_names__true(line):
    assert check_lowercase_family_names(line) is True


@pytest.mark.parametrize(
    'line',
    [
        # undefined values are ok
        'inherit =',
        'inherit =  ',
        # none, None and root are ok
        'inherit = none',
        'inherit = None',
        'inherit = root',
        # whitespace & trailing commas
        'inherit = None,',
        'inherit = None, ',
        '  inherit  =  None  ,  ',
        # uppercase family names are ok
        'inherit = None, FOO, BAR',
        'inherit = FOO',
        'inherit = FOO_BAR_0',
        # parameters should be ignored
        'inherit = A<a>Z',
        'inherit = <a=1, b-1, c+1>',
        # jinja2 should be ignored
        param(
            'inherit = A{{ a }}Z, {% for x in range(5) %}'
            'A{{ x }}, {% endfor %}',
            id='jinja2-long'
        ),
        # trailing comments should be ignored
        'inherit = A, B # no, comment',
        'inherit = # a',
        # quotes are ok
        'inherit = "A", "B"',
        "inherit = 'A', 'B'",
        'inherit = "None", B',
        'inherit = <a = 1, b - 1>',
        # one really awkward, but valid example
        param(
            'inherit = none, FOO_BAR_0, "<a - 1>", A<a>Z, A{{a}}Z',
            id='awkward'
        ),
    ]
)
def test_check_lowercase_family_names__false(line):
    assert check_lowercase_family_names(line) is False


def test_inherit_lowercase_matches():
    lint = lint_text('inherit = a', ['style'])
    assert any('S007' in msg for msg in lint.messages)


@pytest.mark.parametrize(
    # 8 and 11 won't be tested because there is no jinja2 shebang
    'number', set(range(1, len(STYLE_CHECKS) + 1)) - {8, 11}
)
def test_check_cylc_file_lint(number):
    lint = lint_text(LINT_TEST_FILE, ['style'])
    assert_contains(lint.messages, f'S{number:03d}')


@pytest.mark.parametrize('code', STYLE_CHECKS.keys())
def test_check_exclusions(code):
    """It does not report any items excluded."""
    lint = lint_text(LINT_TEST_FILE, ['style'], [code])
    assert not filter_strings(lint.messages, code)


def test_check_cylc_file_jinja2_comments():
    """Jinja2 inside a Jinja2 comment should not warn"""
    lint = lint_text('#!jinja2\n{# {{ foo }} #}', ['style'])
    assert not any('S011' in msg for msg in lint.messages)


def test_check_cylc_file_jinja2_comments_shell_arithmetic_not_warned():
    """Jinja2 after a $((10#$variable)) should not warn"""
    lint = lint_text('#!jinja2\na = b$((10#$foo+5)) {{ BAR }}', ['style'])
    assert not any('S011' in msg for msg in lint.messages)


@pytest.mark.parametrize(
    # 11 won't be tested because there is no jinja2 shebang
    'number', set(range(1, len(MANUAL_DEPRECATIONS) + 1)) - {11}
)
def test_check_cylc_file_inplace(number):
    lint = lint_text(TEST_FILE, ['728', 'style'], modify=True)
    # U0008 Has been removed, but we don't want to change the numbering
    if number != 8:
        assert_contains(lint.outlines, f'[U{number:03d}]')


def test_get_cylc_files_get_all_rcs(tmp_path):
    """It returns all paths except `log/**`.
    """
    expect = [('etc', 'foo.rc'), ('bin', 'foo.rc'), ('an_other', 'foo.rc')]

    # Create a fake run directory, including the log file which should not
    # be searched:
    dirs = ['etc', 'bin', 'log', 'an_other', 'log/skarloey/']
    for path in dirs:
        thispath = tmp_path / path
        thispath.mkdir(parents=True)
        (thispath / 'foo.rc').touch()

    # Run the test
    result = [(i.parent.name, i.name) for i in get_cylc_files(tmp_path)]
    assert sorted(result) == sorted(expect)


def mock_parse_checks(*args, **kwargs):
    return {
        'U042': {
            'short': 'section `[vizualization]` has been removed.',
            'url': 'some url or other',
            'purpose': 'U',
            'rst': 'section ``[vizualization]`` has been removed.',
            'function': re.compile('not a regex')
        },
    }


def test_get_reference_rst(monkeypatch):
    """It produces a reference file for our linting."""
    monkeypatch.setattr(
        'cylc.flow.scripts.lint.parse_checks', mock_parse_checks
    )
    ref = get_reference('all', 'rst')
    expect = (
        '\n7 to 8 upgrades\n---------------\n\n'
        '`U042 <https://cylc.github.io/cylc-doc/stable'
        '/html/7-to-8/some url or other>`_'
        f'\n{"^" * 78}'
        '\nsection ``[vizualization]`` has been '
        'removed.\n\n\n'
    )
    assert ref == expect


def test_get_reference_text(monkeypatch):
    """It produces a reference file for our linting."""
    monkeypatch.setattr(
        'cylc.flow.scripts.lint.parse_checks', mock_parse_checks
    )
    ref = get_reference('all', 'text')
    expect = (
        '\n7 to 8 upgrades\n---------------\n\n'
        'U042:\n    section `[vizualization]` has been '
        'removed.'
        '\n    https://cylc.github.io/cylc-doc/stable/html/7-to-8/some'
        ' url or other\n\n\n'
    )
    assert ref == expect


@pytest.fixture()
def fixture_get_deprecations():
    """Get the deprections list for cylc.flow.cfgspec.workflow"""
    deprecations = get_upgrader_info()
    return deprecations


@pytest.mark.parametrize(
    'findme',
    [
        pytest.param(
            'abort if any task fails =',
            id='Item not available at Cylc 8'
        ),
        pytest.param(
            'timeout =',
            id='Item renamed at Cylc 8'
        ),
        pytest.param(
            '!execution retry delays',
            id='Item moved, name unchanged at Cylc 8'
        ),
        pytest.param(
            '[cylc]',
            id='Section changed at Cylc 8'
        ),
    ]
)
def test_get_upg_info(fixture_get_deprecations, findme):
    """It correctly scrapes the Cylc upgrader object.

    n.b this is just sampling to ensure that the test it getting items.
    """
    if findme.startswith('!'):
        assert not any(
            i['function'](findme) for i in fixture_get_deprecations.values()
        )
    else:
        assert any(
            i['function'](findme) for i in fixture_get_deprecations.values()
        ) is True


@pytest.mark.parametrize(
    'settings, expected',
    [
        param(
            """
            rulesets = ['style']
            ignore = ['S004']
            exclude = ['sites/*.cylc']
            """,
            {
                'rulesets': ['style'],
                'ignore': ['S004'],
                'exclude': ['sites/*.cylc'],
                'max-line-length': None,
            },
            id="returns what we want"
        ),
        param(
            """
            northgate = ['sites/*.cylc']
            mons-meg = 42
            """,
            (CylcError, ".*northgate"),
            id="invalid settings fail validation"
        ),
        param(
            "max-line-length = 22",
            {
                'exclude': [],
                'ignore': [],
                'rulesets': [],
                'max-line-length': 22,
            },
            id='sets max line length'
        )
    ]
)
def test_get_pyproject_toml(tmp_path, settings, expected):
    """It returns only the lists we want from the toml file."""
    tomlcontent = "[tool.cylc.lint]\n" + dedent(settings)
    (tmp_path / 'pyproject.toml').write_text(tomlcontent)

    if isinstance(expected, tuple):
        exc, match = expected
        with pytest.raises(exc, match=match):
            get_pyproject_toml(tmp_path)
    else:
        assert get_pyproject_toml(tmp_path) == expected


@pytest.mark.parametrize(
    'tomlfile',
    [None, '', '[tool.cylc.lint]', '[cylc-lint]']
)
def test_get_pyproject_toml_returns_blank(tomlfile, tmp_path):
    if tomlfile is not None:
        tfile = (tmp_path / 'pyproject.toml')
        tfile.write_text(tomlfile)
    expect = {
        'exclude': [], 'ignore': [], 'max-line-length': None, 'rulesets': []
    }
    assert get_pyproject_toml(tmp_path) == expect


def test_get_pyproject_toml__depr(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    """It warns if the section is deprecated."""
    file = tmp_path / 'pyproject.toml'
    caplog.set_level(logging.WARNING)

    file.write_text(f'[{LINT_SECTION}]\nmax-line-length=14')
    assert get_pyproject_toml(tmp_path)['max-line-length'] == 14
    assert not caplog.text

    file.write_text('[cylc-lint]\nmax-line-length=17')
    assert get_pyproject_toml(tmp_path)['max-line-length'] == 17
    assert "[cylc-lint] section in pyproject.toml is deprecated" in caplog.text


@pytest.mark.parametrize(
    'input_, output',
    [
        param(
            {'exclude': ['hey', 'there', 'Delilah']},
            True,
            id='it works'
        ),
        param(
            {'foo': ['hey', 'there', 'Delilah', 42]},
            'allowed',
            id='it fails with illegal section name'
        ),
        param(
            {'exclude': 'woo!'},
            'should be a list, but',
            id='it fails with illegal section type'
        ),
        param(
            {'exclude': ['hey', 'there', 'Delilah', 42]},
            'should be a string',
            id='it fails with illegal value name'
        ),
        param(
            {'rulesets': ['hey']},
            'hey not valid: Rulesets can be',
            id='it fails with illegal ruleset'
        ),
        param(
            {'ignore': ['hey']},
            'hey not valid: Ignore codes',
            id='it fails with illegal ignores'
        ),
        param(
            {'ignore': ['R999']},
            'R999 is a not a known linter code.',
            id='it fails with non-existant checks ignored'
        ),
        param(
            {'ignore': ['U008']},
            'warn',
            id='valid, but deprecated linter code'
        ),
    ]
)
def test_validate_toml_items(input_, output, caplog):
    """It chucks out the wrong sort of items."""
    if output not in [True, 'warn']:
        with pytest.raises(CylcError, match=output):
            validate_toml_items(input_)
    elif output is True:
        assert validate_toml_items(input_) is output
    elif output == 'warn':
        assert validate_toml_items(input_) is True
        assert 'U008 is a deprecated linter code' in caplog.messages



@pytest.mark.parametrize(
    'clidata, tomldata, expect',
    [
        param(
            {
                'rulesets': ['foo', 'bar'],
                'ignore': ['R101'],
            },
            {
                'rulesets': ['baz'],
                'ignore': ['R100'],
                'exclude': ['not_me-*.cylc']
            },
            {
                'rulesets': ['foo', 'bar'],
                'ignore': ['R100', 'R101'],
                'exclude': ['not_me-*.cylc'],
                'max-line-length': None
            },
            id='It works with good path'
        ),
    ]
)
def test_merge_cli_with_tomldata(clidata, tomldata, expect):
    """It merges each of the three sections correctly: see function.__doc__"""
    assert _merge_cli_with_tomldata(clidata, tomldata) == expect


def test_invalid_tomlfile(tmp_path):
    """It fails nicely if pyproject.toml is malformed"""
    tomlfile = (tmp_path / 'pyproject.toml')
    tomlfile.write_text('foo :{}')
    expected_msg = 'pyproject.toml did not load:'
    with pytest.raises(CylcError, match=expected_msg):
        get_pyproject_toml(tmp_path)


@pytest.mark.parametrize(
    'ref, expect',
    [
        [True, 'line > ``<max_line_len>`` characters'],
        [False, 'line > 42 characters']
    ]
)
def test_parse_checks_reference_mode(ref, expect):
    """Add extra explanation of max line legth setting in reference mode.
    """
    result = parse_checks(['style'], reference=ref, max_line_len=42)
    value = result['S012']
    assert expect in value['short']


@pytest.mark.parametrize(
    'spaces, expect',
    (
        (0, 'S002'),
        (1, 'S013'),
        (2, 'S013'),
        (3, 'S013'),
        (4, None),
        (5, 'S013'),
        (6, 'S013'),
        (7, 'S013'),
        (8, None),
        (9, 'S013')
    )
)
def test_indents(spaces, expect):
    """Test different wrong indentations

    Parameterization deliberately over-obvious to avoid replicating
    arithmetic logic from code. Dangerously close to re-testing ``%``
    builtin.
    """
    result = lint_text(
        f"{' ' * spaces}foo = 42",
        ['style']
    )
    result = ''.join(result.messages)
    if expect:
        assert expect in result
    else:
        assert not result


def test_noqa():
    """Comments turn of checks.

    """
    output = lint_text(
        'foo = bar#noqa\n'
        'qux = baz # noqa: S002\n'
        'buzz = food # noqa: S007\n'
        'quixotic = foolish # noqa: S007, S992 S002\n',
        ['style']
    )
    assert len(output.messages) == 1
    assert 'flow.cylc:3' in output.messages[0]
