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
"""Tests `cylc lint` CLI Utility.

TODO: Consider tests in unit test file for movement to here.
"""

import pytest

from cylc.flow.scripts.lint import main, get_option_parser

cylc_lint = main.__wrapped__


@pytest.fixture
def setup():
    parser = get_option_parser()
    options = parser.get_default_values()
    return parser, options


def test_lint_empty_file(tmp_path, setup, caplog):
    """Argument --rule is mutually exclusive of either --ignores
    and --ruleset.
    """
    (tmp_path / 'flow.cylc').touch()
    parser, options = setup
    with pytest.raises(SystemExit, match="True"):
        main.__wrapped__(parser, options, str(tmp_path))
    assert 'File flow.cylc is empty.' in caplog.messages


def test_mutually_exclusive_args(tmp_path, setup):
    """Argument --rule is mutually exclusive of either --ignores
    and --ruleset.
    """
    (tmp_path / 'flow.cylc').write_text('[hi]')
    parser, options = setup
    options.rule = ['S002']

    # Rule + Ruleset
    options.ruleset = '728'
    with pytest.raises(SystemExit, match="1"):
        main.__wrapped__(parser, options, str(tmp_path))

    # Rule + Ignores
    options.ignores = ['S005']
    options.ruleset = ''
    with pytest.raises(SystemExit, match="1"):
        main.__wrapped__(parser, options, str(tmp_path))


def test_single_check_cli(setup, tmp_path, caplog):
    """Demo that CLI --rule option works.
    """
    (tmp_path / 'flow.cylc').write_text('    [meta]')
    parser, options = setup

    # This rule should cause a failure:
    options.rule = ['S003']
    with pytest.raises(SystemExit, match="True"):
        main.__wrapped__(parser, options, str(tmp_path))
    assert (
        'Checking only S003: Top level sections should'
        ' not be indented.'
    ) in caplog.messages

    # This rule should NOT cause a failure:
    options.ruleset = ''
    options.rule = ['S001']
    with pytest.raises(SystemExit, match="False"):
        main.__wrapped__(parser, options, str(tmp_path))
    assert (
        'Checking only S001: Use multiple spaces, not tabs'
    ) in caplog.messages
