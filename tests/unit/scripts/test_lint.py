#!/usr/bin/env python3
# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#PID: 12632 Threads: 1 RSS: 1044

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Tests `cylc lint` CLI Utility.
"""
import difflib
from pathlib import Path
import pytest
from pytest import param
import re

from cylc.flow.scripts.lint import (
    MANUAL_DEPRECATIONS,
    check_cylc_file,
    get_cylc_files,
    get_reference_rst,
    get_reference_text,
    get_pyproject_toml,
    get_upgrader_info,
    merge_cli_with_tomldata,
    parse_checks,
    validate_toml_items
)
from cylc.flow.exceptions import CylcError

STYLE_CHECKS = parse_checks(['style'])
UPG_CHECKS = parse_checks(['728'])

TEST_FILE = """
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
            graph = MyFaM:finish-all => remote => !mash_theme

[runtime]
    [[MyFaM]]
        extra log files = True
        {% from 'cylc.flow' import LOG %}
        pre-script = "echo ${CYLC_SUITE_DEF_PATH}"
        script = {{HELLOWORLD}}
        post-script = "echo ${CYLC_SUITE_INITIAL_CYCLE_TIME}"
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
            expired handler = dafuhj
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

"""


LINT_TEST_FILE = """
\t[scheduler]

 [scheduler]

[[dependencies]]

{% set   N = 009 %}
{% foo %}
{{foo}}
# {{quix}}

[runtime]
          [[foo]]
        inherit = hello
     [[[job]]]
something\t
    [[bar]]
        platform = $(some-script foo)
    [[baz]]
        platform = `no backticks`
"""

LINT_TEST_FILE += (
    '\nscript = the quick brown fox jumps over the lazy dog,'
    ' Sphinx of black quartz hear my vow,'
    ' Lorum ipsum doobity doo'
    ' until it becomes clear that this line'
    ' is far longer the 79 characters.')


@pytest.fixture()
def create_testable_file(monkeypatch, capsys):
    def _inner(test_file, checks, ignores=None):
        if ignores is None:
            ignores = []
        monkeypatch.setattr(Path, 'read_text', lambda _: test_file)
        checks = parse_checks(checks, ignores)
        check_cylc_file(Path('flow.cylc'), Path('flow.cylc'), checks)
        return capsys.readouterr(), checks
    return _inner


@pytest.mark.parametrize('number', range(1, len(MANUAL_DEPRECATIONS) + 1))
def test_check_cylc_file_7to8(create_testable_file, number, capsys):
    """TEST File has one of each manual deprecation;"""
    result, checks = create_testable_file(TEST_FILE, ['728'])
    if number in [11]:  # Assert that tests requiring a jinja2 shebang not run.
        assert f'[U{number:03d}]' not in result.out
    else:
        assert f'[U{number:03d}]' in result.out


def test_check_cylc_file_7to8_auto(create_testable_file, capsys):
    """TEST_FILE has the same number of results as before."""
    result, checks = create_testable_file(TEST_FILE, ['728'])
    assert len([i for i in result.out.split('\n') if '998' in i]) == 36
    assert len([i for i in result.out.split('\n') if '999' in i]) == 28


def test_check_cylc_file_7to8_has_shebang(create_testable_file):
    """Jinja2 code comments will not be added if shebang present"""
    result, _ = create_testable_file('#!jinja2\n{{FOO}}', '', '[scheduler]')
    result = result.out
    assert result == ''


def test_check_cylc_file_line_no(create_testable_file, capsys):
    """It prints the correct line numbers"""
    result, _ = create_testable_file(TEST_FILE, ['728'])
    result = result.out
    assert result.split()[1] == '.:2:'


@pytest.mark.parametrize(
    'inherit_line',
    (
        'inherit = foo, b, a, r',
        'inherit = FOO, bar',
        'inherit = None, bar',
        'inherit = g',
        'inherit = B, None',
    )
)
def test_inherit_lowercase_matches(create_testable_file, inherit_line):
    result, _ = create_testable_file(inherit_line, ['style'])
    assert 'S007' in result.out


@pytest.mark.parametrize(
    'inherit_line',
    (
        'inherit = None',
        'inherit = None,',
        'inherit = None, FOO',
    )
)
def test_inherit_lowercase_not_match_none(create_testable_file, inherit_line):
    result, _ = create_testable_file(inherit_line, ['style'])
    assert 'S007' not in result.out


@pytest.mark.parametrize(
    # 8 and 11 Won't be tested because there is no jinja2 shebang.
    'code', [i for i in range(1, len(STYLE_CHECKS) + 1) if i not in [8, 11]]
)
def test_check_cylc_file_lint(create_testable_file, code):
    result, _ = create_testable_file(LINT_TEST_FILE, ['style'])
    assert f'S{code:03d}' in result.out


@pytest.mark.parametrize('exclusion', [i for i in STYLE_CHECKS.keys()])
def test_check_exclusions(create_testable_file, exclusion):
    """It does not report any items excluded."""
    result, _ = create_testable_file(
        LINT_TEST_FILE, ['style'], [exclusion])
    assert exclusion not in result.out


def test_check_cylc_file_jinja2_comments(create_testable_file):
    # Replace the '# {{' line to be '{# {{' which should not be a warning
    result, _ = create_testable_file('#!jinja2\n{# {{ foo }} #}', ['style'])
    assert 'S011' not in result.out


@pytest.fixture
def create_testable_dir(tmp_path):
    test_file = (tmp_path / 'suite.rc')
    test_file.write_text(TEST_FILE)
    check_cylc_file(
        test_file.parent,
        test_file,
        parse_checks(['728', 'style']),
        modify=True,
    )
    return '\n'.join([*difflib.Differ().compare(
        TEST_FILE.split('\n'), test_file.read_text().split('\n')
    )])


@pytest.mark.parametrize(
    'number', range(1, len(MANUAL_DEPRECATIONS) + 1)
)
def test_check_cylc_file_inplace(create_testable_dir, number):
    if number in [8, 11]:
        # number 8 should only be reported for *.cylc files - this test uses
        # a suite.rc
        assert f'[U{number:03d}]' not in create_testable_dir
    else:
        assert f'[U{number:03d}]' in create_testable_dir


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


MOCK_CHECKS = {
    'U042': {
        'short': 'section `[vizualization]` has been removed.',
        'url': 'some url or other',
        'purpose': 'U',
        'rst': 'section ``[vizualization]`` has been removed.',
        'function': re.compile('not a regex')
    },
}


def test_get_reference_rst():
    """It produces a reference file for our linting."""
    ref = get_reference_rst(MOCK_CHECKS)
    expect = (
        '\n7 to 8 upgrades\n---------------\n\n'
        'U042\n^^^^\nsection ``[vizualization]`` has been '
        'removed.\n\n\n'
    )
    assert ref == expect


def test_get_reference_text():
    """It produces a reference file for our linting."""
    ref = get_reference_text(MOCK_CHECKS)
    expect = (
        '\n7 to 8 upgrades\n---------------\n\n'
        'U042:\n    section `[vizualization]` has been '
        'removed.\n\n\n'
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
        assert not any(
            i['function'](findme) for i in fixture_get_deprecations.values()
        )


@pytest.mark.parametrize(
    'expect',
    [
        param({
            'rulesets': ['style'],
            'ignore': ['S004'],
            'exclude': ['sites/*.cylc']},
            id="it returns what we want"
        ),
        param({
            'northgate': ['sites/*.cylc'],
            'mons-meg': 42},
            id="it only returns requested sections"
        ),
        param({
            'max-line-length': 22},
            id='it sets max line length'
        )
    ]
)
def test_get_pyproject_toml(tmp_path, expect):
    """It returns only the lists we want from the toml file."""
    tomlcontent = "[cylc-lint]"
    permitted_keys = ['rulesets', 'ignore', 'exclude', 'max-line-length']

    for section, value in expect.items():
        tomlcontent += f'\n{section} = {value}'
    (tmp_path / 'pyproject.toml').write_text(tomlcontent)
    tomldata = get_pyproject_toml(tmp_path)

    control = {}
    for key in permitted_keys:
        control[key] = expect.get(key, [])
    assert tomldata == control


@pytest.mark.parametrize('tomlfile', [None, '', '[cylc-lint]'])
def test_get_pyproject_toml_returns_blank(tomlfile, tmp_path):
    if tomlfile is not None:
        tfile = (tmp_path / 'pyproject.toml')
        tfile.write_text(tomlfile)
    expect = {k: [] for k in {
        'exclude', 'ignore', 'max-line-length', 'rulesets'
    }}
    assert get_pyproject_toml(tmp_path) == expect


@pytest.mark.parametrize(
    'input_, error',
    [
        param(
            {'exclude': ['hey', 'there', 'Delilah']},
            None,
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
        )
    ]
)
def test_validate_toml_items(input_, error):
    """It chucks out the wrong sort of items."""
    if error is not None:
        with pytest.raises(CylcError, match=error):
            validate_toml_items(input_)
    else:
        assert validate_toml_items(input_) is True


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
    assert merge_cli_with_tomldata(clidata, tomldata) == expect


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
        [False, 'line > 130 characters']
    ]
)
def test_parse_checks_reference_mode(ref, expect):
    result = parse_checks(['style'], reference=ref)
    key = list(result.keys())[-1]
    value = result[key]
    assert expect in value['short']
