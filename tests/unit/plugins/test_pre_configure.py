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
""""Test the pre_configure entry point."""

from functools import partial
from itertools import permutations
from random import random

import pytest

from cylc.flow.exceptions import PluginError
from cylc.flow.parsec.exceptions import ParsecError
from cylc.flow.parsec.fileparse import process_plugins


class EntryPointWrapper:
    """Wraps a method to make it look like an entry point."""

    def __init__(self, fcn):
        self.name = getattr(fcn, '__name__', str(fcn))
        self.fcn = fcn

    def load(self):
        return self.fcn


@EntryPointWrapper
def pre_configure_basic(*_, **__):
    """Simple plugin that returns one env var and one template var."""
    return {
        'env': {
            'ANSWER': '42'
        },
        'template_variables': {
            'QUESTION': 'What do you get if you multiply 7 by 6?'
        }
    }


@EntryPointWrapper
def pre_configure_templating_detected(*_, **__):
    """Plugin that detects a random templating engine."""
    return {
        'templating_detected': str(random())
    }


@EntryPointWrapper
def pre_configure_error(*_, **__):
    """Plugin that raises an exception."""
    raise Exception('foo')


def test_pre_configure(monkeypatch):
    """It should call the plugin."""
    monkeypatch.setattr(
        'cylc.flow.plugins.iter_entry_points',
        lambda namespace: (
            [pre_configure_basic] if namespace == 'cylc.pre_configure' else []
        )
    )
    extra_vars = process_plugins('/', None)
    assert extra_vars == {
        'env': {
            'ANSWER': '42'
        },
        'template_variables': {
            'QUESTION': 'What do you get if you multiply 7 by 6?'
        },
        'templating_detected': None
    }


def test_pre_configure_duplicate(monkeypatch):
    """It should error when plugins clash."""
    monkeypatch.setattr(
        'cylc.flow.plugins.iter_entry_points',
        lambda namespace: (
            [
                pre_configure_basic,
                pre_configure_basic,
            ] if namespace == 'cylc.pre_configure' else []
        )
    )
    with pytest.raises(ParsecError):
        process_plugins('/', None)


def test_pre_configure_templating_detected(monkeypatch):
    """It should error when plugins clash (for templating)."""
    monkeypatch.setattr(
        'cylc.flow.plugins.iter_entry_points',
        lambda namespace: (
            [
                pre_configure_templating_detected,
                pre_configure_templating_detected,
            ] if namespace == 'cylc.pre_configure' else []
        )
    )
    with pytest.raises(ParsecError):
        process_plugins('/', None)


def test_pre_configure_exception(monkeypatch):
    """It should wrap plugin errors."""
    monkeypatch.setattr(
        'cylc.flow.plugins.iter_entry_points',
        lambda namespace: (
            [
                pre_configure_error,
            ] if namespace == 'cylc.pre_configure' else []
        )
    )
    with pytest.raises(PluginError) as exc_ctx:
        process_plugins('/', None)
    # the context of the original error should be preserved in the raised
    # exception
    assert exc_ctx.value.entry_point == 'cylc.pre_configure'
    assert exc_ctx.value.plugin_name == 'pre_configure_error'
    assert str(exc_ctx.value.exc) == 'foo'


def _pre_configure(*a, templating_detected=None, **k):
    """A mock pre-configure plugin where templating_detected can be overridden.
    """
    return {
        'env': {},
        'template_variables': {},
        'templating_detected': templating_detected,
    }


@pytest.mark.parametrize(
    'plugins',
    permutations(
        [
            # four plugins which return differing, but compatible results
            EntryPointWrapper(
                partial(_pre_configure, templating_detected='a')
            ),
            EntryPointWrapper(
                partial(_pre_configure, templating_detected='a')
            ),
            EntryPointWrapper(
                partial(_pre_configure, templating_detected=None)
            ),
            EntryPointWrapper(
                partial(_pre_configure, templating_detected=None)
            ),
        ],
    ),
)
def test_pre_configure_multiple_compatible(monkeypatch, plugins):
    """The order in which plugins are run shouldn't affect templating_detected.

    See https://github.com/cylc/cylc-rose/issues/440
    """
    monkeypatch.setattr(
        'cylc.flow.plugins.iter_entry_points',
        lambda namespace: plugins if namespace == 'cylc.pre_configure' else [],
    )
    extra_vars = process_plugins('/', None)
    assert extra_vars['templating_detected'] == 'a'
