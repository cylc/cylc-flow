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

from functools import partial

import pytest

from cylc.flow.exceptions import CylcError, WorkflowStopped
from cylc.flow.network.multi import _report, _process_response
from cylc.flow.terminal import DIM


def response(success, msg, operation='set'):
    return {
        operation: {
            'result': [{'id': '~user/workflow', 'response': [success, msg]}]
        }
    }


def test_report_valid(monkeypatch):
    """It should report command outcome."""
    monkeypatch.setattr('cylc.flow.flags.verbosity', 0)

    # fail case
    assert _report(response(False, 'MyError')) == (
        None,
        '<red>MyError</red>',
        False,
    )

    # success case
    assert _report(response(True, '12345')) == (
        '<green>Command queued</green>',
        None,
        True,
    )

    # success case (debug mode)
    monkeypatch.setattr('cylc.flow.flags.verbosity', 1)
    assert _report(response(True, '12345')) == (
        f'<green>Command queued</green> <{DIM}>id=12345</{DIM}>',
        None,
        True,
    )


def test_report_invalid(monkeypatch):
    """It should report invalid responses.

    Tests that the code behaves as well as can be expected when confronted with
    responses which should not be possible.
    """
    # test "None" response
    monkeypatch.setattr('cylc.flow.flags.verbosity', 0)
    assert _report({'set': None}) == (
        None,
        '<red>Error processing command:'
        "\n    TypeError: 'NoneType' object is not subscriptable</red>",
        False,
    )

    # test "None" response in debug mode
    monkeypatch.setattr('cylc.flow.flags.verbosity', 2)
    assert _report({'set': None}) == (
        None,
        '<red>Error processing command:'
        "\n    TypeError: 'NoneType' object is not subscriptable</red>"
        # the response should be output in debug mode
        "\n    <fg 248>response={'set': None}</fg 248>",
        False,
    )

    # test multiple mutations in one operation (not supported)
    monkeypatch.setattr('cylc.flow.flags.verbosity', 0)
    assert _report(
        {
            **response(True, '12345'),
            **response(True, '23456', 'trigger'),
        }
    ) == (
        None,
        '<red>Error processing command:'
        '\n    NotImplementedError:'
        ' Cannot process multiple mutations in one operation.</red>',
        False,
    )

    # test zero mutations in the operation
    assert _report(
        {}
    ) == (
        None,
        '<red>Error processing command:'
        '\n    Exception: {}</red>',
        False,
    )


def test_process_response(monkeypatch):
    """It should handle exceptions and return processed results."""
    def report(exception_class, _response):
        raise exception_class('xxx')

    class Foo(Exception):
        pass

    # WorkflowStopped -> fail case
    monkeypatch.setattr('cylc.flow.flags.verbosity', 0)
    assert _process_response(partial(report, WorkflowStopped), {}) == (
        None,
        '<yellow>WorkflowStopped: xxx is not running</yellow>',
        False,
    )

    # WorkflowStopped -> success case for this command
    monkeypatch.setattr('cylc.flow.flags.verbosity', 0)
    assert _process_response(
        partial(report, WorkflowStopped),
        {},
        # this overrides the default interpretation of "WorkflowStopped" as a
        # fail case
        success_exceptions=(WorkflowStopped,),
    ) == (
        '<green>WorkflowStopped: xxx is not running</green>',
        None,
        True,  # success outcome
    )

    # CylcError -> expected error, log it
    monkeypatch.setattr('cylc.flow.flags.verbosity', 0)
    assert _process_response(partial(report, CylcError), {}) == (
        None,
        '<red>CylcError: xxx</red>',
        False,
    )

    # CylcError -> expected error, raise it (debug mode)
    monkeypatch.setattr('cylc.flow.flags.verbosity', 2)
    with pytest.raises(CylcError):
        _process_response(partial(report, CylcError), {})

    # Exception -> unexpected error, raise it
    monkeypatch.setattr('cylc.flow.flags.verbosity', 0)
    with pytest.raises(Foo):
        _process_response(partial(report, Foo), {})
