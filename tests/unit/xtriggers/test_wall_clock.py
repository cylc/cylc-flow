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

from cylc.flow.xtriggers.wall_clock import _wall_clock, validate
from metomi.isodatetime.parsers import DurationParser
import pytest
from pytest import param


@pytest.mark.parametrize('trigger_time, expected', [
    (499, True),
    (500, False),
])
def test_wall_clock(
    monkeypatch: pytest.MonkeyPatch, trigger_time: int, expected: bool
):
    monkeypatch.setattr(
        'cylc.flow.xtriggers.wall_clock.time', lambda: 500
    )
    assert _wall_clock(trigger_time) == expected


@pytest.fixture
def monkeypatch_interval_parser(monkeypatch):
    """Interval parse only works normally if a WorkflowSpecifics
    object identify the parser to be used.
    """
    monkeypatch.setattr(
        'cylc.flow.xtriggers.wall_clock.interval_parse',
        DurationParser().parse
    )


def test_validate_good(monkeypatch_interval_parser):
    validate({'offset': 'PT1H'})


@pytest.mark.parametrize(
    'args, err', (
        param({'offset': 1}, "^Invalid", id='invalid-offset-int'),
        param({'offset': 'Zaphod'}, "^Invalid", id='invalid-offset-str'),
    )
)
def test_validate_exceptions(
    monkeypatch_interval_parser, args, err
):
    with pytest.raises(Exception, match=err):
        validate(args)
