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
"""Tests `cylc lint` CLI Utility.
"""
import difflib
from pathlib import Path
import pytest
import re

from cylc.flow.scripts.lint import (
    CHECKS,
    check_cylc_file,
    get_cylc_files,
    get_reference_rst,
    parse_checks
)


TEST_FILE = """
[visualization]

[cylc]
    include at start-up = foo
    exclude at start-up = bar
    log resolved dependencies = True
    required run mode = False
    health check interval = PT10M
    abort if any task fails = true
    suite definition directory = '/woo'
    disable automatic shutdown = false
    reference test = true
    spawn to max active cycle points = false
    [[simulation]]
        disable suite event handlers = true
    [[authentication]]
    [[environment]]
    force run mode = dummy
    [[events]]
        abort on stalled = True
        abort if startup handler fails= True  # deliberately not added a space.
        abort if shutdown handler fails= True
        abort if timeout handler fails = True
        abort if stalled handler fails = True
        abort if inactivity handler fails = False
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
            graph = foo



[runtime]
    [[MYFAM]]
        extra log files = True
        {% from 'cylc.flow' import LOG %}
        script = {{HELLOWORLD}}
        suite state polling = PT1H
        [[[remote]]]
            host = parasite
            suite definition directory = '/home/bar'
        [[[job]]]
            batch system = slurm
            shell = fish
        [[[events]]]
            mail retry delays = PT30S
            warning handler = frr.sh

"""


LINT_TEST_FILE = """
\t[scheduler]

 [scheduler]

[[dependencies]]

[runtime]
          [[foo]]
        inherit = hello
     [[[job]]]
something\t
"""

LINT_TEST_FILE += ('\nscript = the quick brown fox jumps over the lazy dog '
    'until it becomes clear that this line is far longer the 79 characters.')


@pytest.fixture()
def create_testable_file(monkeypatch, capsys):
    def _inner(test_file, checks):
        monkeypatch.setattr(Path, 'read_text', lambda _: test_file)
        check_cylc_file(Path('x'), parse_checks(checks))
        return capsys.readouterr()
    return _inner


@pytest.mark.parametrize(
    'number', range(len(CHECKS['U']))
)
def test_check_cylc_file_7to8(create_testable_file, number, capsys):
    try:
        result = create_testable_file(TEST_FILE, '728').out
        assert f'[U{number:03d}]' in result
    except AssertionError:
        raise AssertionError(
            f'missing error number U{number:03d}'
            f'{[*CHECKS["U"].keys()][number]}'
        )


def test_check_cylc_file_7to8_has_shebang(create_testable_file):
    """Jinja2 code comments will not be added if shebang present"""
    result = create_testable_file('#!jinja2\n{{FOO}}', '[scheduler]').out
    assert result == ''

def test_check_cylc_file_line_no(create_testable_file, capsys):
    """It prints the correct line numbers"""
    result = create_testable_file(TEST_FILE, '728').out
    assert result.split()[1] == '2:'


@pytest.mark.parametrize(
    'number', range(len(CHECKS['S']))
)
def test_check_cylc_file_lint(create_testable_file, number):
    try:
        assert f'[S{number:03d}]' in create_testable_file(
            LINT_TEST_FILE, 'lint').out
    except AssertionError:
        raise AssertionError(
            f'missing error number S:{number:03d}'
            f'{[*CHECKS["S"].keys()][number]}'
        )


@pytest.fixture
def create_testable_dir(tmp_path):
    test_file = (tmp_path / 'suite.rc')
    test_file.write_text(TEST_FILE)
    check_cylc_file(test_file, parse_checks('all'), modify=True)
    return '\n'.join([*difflib.Differ().compare(
        TEST_FILE.split('\n'), test_file.read_text().split('\n')
    )])


@pytest.mark.parametrize(
    'number', range(len(CHECKS['U']))
)
def test_check_cylc_file_inplace(create_testable_dir, number):
    try:
        assert f'[U{number:03d}]' in create_testable_dir
    except AssertionError:
        raise AssertionError(
            f'missing error number {number:03d}:7-to-8 - '
            f'{[*CHECKS["U"].keys()][number]}'
        )


def test_get_cylc_files_get_all_rcs(tmp_path):
    """It returns all paths except `log/**`.
    """
    expect = [('etc', 'foo.rc'), ('bin', 'foo.rc'), ('an_other', 'foo.rc')]

    # Create a fake run directory, including the log file which should not
    # be searched:
    dirs = ['etc', 'bin', 'log', 'an_other']
    for path in dirs:
        thispath = tmp_path / path
        thispath.mkdir()
        (thispath / 'foo.rc').touch()

    # Run the test
    result = [(i.parent.name, i.name) for i in get_cylc_files(tmp_path)]
    assert result.sort() == expect.sort()


def test_get_reference():
    """It produces a reference file for our linting."""
    ref = get_reference({
        re.compile('not a regex'): {
            'short': 'section `[vizualization]` has been removed.',
            'url': 'some url or other',
            'purpose': 'U',
            'index': 42
        },
    })
    expect = (
        '\n7 to 8 upgrades\n---------------\n\n'
        'U042 ``not a regex``:\n    section `[vizualization]` has been '
        'removed.\n    see -'
        ' https://cylc.github.io/cylc-doc/latest/html/7-to-8/some url'
        ' or other\n\n'
    )
    assert ref == expect
