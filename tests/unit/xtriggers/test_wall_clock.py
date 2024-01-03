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

from cylc.flow.exceptions import WorkflowConfigError
from cylc.flow.xtriggers.wall_clock import validate
from metomi.isodatetime.parsers import DurationParser
import pytest
from pytest import param


@pytest.fixture
def monkeypatch_interval_parser(monkeypatch):
    """Interval parse only works normally if a WorkflowSpecifics
    object identify the parser to be used.
    """
    monkeypatch.setattr(
        'cylc.flow.xtriggers.wall_clock.interval_parse',
        DurationParser().parse
    )


def test_validate_good_path(monkeypatch_interval_parser):
    assert validate([], {}, 'Alles Gut') is None


@pytest.mark.parametrize(
    'args, kwargs, err', (
        param([1, 2], {}, "^Too", id='too-many-args'),
        param([], {'egg': 12}, "^Illegal", id='illegal-arg'),
        param([1], {}, "^Invalid", id='invalid-offset-int'),
        param([], {'offset': 'Zaphod'}, "^Invalid", id='invalid-offset-str'),
    )
)
def test_validate_exceptions(
    monkeypatch_interval_parser, args, kwargs, err
):
    with pytest.raises(WorkflowConfigError, match=err):
        validate(args, kwargs, 'Alles Gut')
