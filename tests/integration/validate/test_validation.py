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
import pytest
from cylc.flow.parsec.exceptions import (
    IllegalValueError,
    IllegalItemError,
    UpgradeError,
)
from cylc.flow.exceptions import (
    GraphParseError,
    WorkflowConfigError,
    PointParsingError,
    SequenceDegenerateError,
)
from metomi.isodatetime.exceptions import (
    TimePointDumperBoundsError,
)


def test_multi_inheritance(flow, validate):
    """Test validating simple multi-inheritance workflows."""
    id_ = flow({
        'scheduling': {
            'graph': {
                'R1': '"""foo"""',
            },
        },
        'runtime': {
            'FOO': {
            },
            'BAR': {
            },
            'foo': {
                'inherit': 'FOO, BAR',
            },
        },
    })
    validate(id_)


def test_periodical(flow, validate):
    """Test validating Daily, Monthly and Yearly type tasks."""
    id_ = flow({
        'scheduling': {
            'initial cycle point': '20100101T00',
            'final cycle point': '20100102T00',
            'graph': {
                'P1D': '"daily"',
                'P1M': '"monthly"',
                'P1Y': '"yearly"',
            },
        },
        'runtime': {
            'root': {
                'script': '"true"',
            },
        },
    })
    validate(id_)


def test_scripting_quotes(flow, validate):
    """Test that validating: script = "foo"bar"baz" fails"""
    id_ = flow({
        'scheduling': {
            'graph': {
                'R1': '"foo"',
            },
        },
        'runtime': {
            'foo': {
                'script': '"foo"bar"baz"',
            },
        },
    })
    with pytest.raises(IllegalValueError, match=(
        r'\(type=string\) \[runtime\]\[foo\].*'
    )):
        validate(id_)


def test_bad_recurrence(flow, validate):
    """Test validation for a bad recurrences"""
    id_ = flow({
        'scheduling': {
            'initial cycle point': '20140101T00',
            'final cycle point': '20140201T00',
            'graph': {
                'R/T00/PT5D': '"foo"',  # PT5D is invalid - should be P5D
            },
        },
        'runtime': {
            'foo': {
                'script': 'true',
            },
        },
    })
    with pytest.raises(WorkflowConfigError, match=(
        r'Cannot process recurrence.*'
    )):
        validate(id_)


def test_fail_cylc6_inter_cycle_syntax(flow, validate):
    """Test validation with a new-style cycle point and a prev-style offset."""
    id_ = flow({
        'scheduling': {
            'initial cycle point': '20100101T00',
            'graph': {
                'T00': '"foo[T-24] => foo"',
            },
        },
    })
    with pytest.raises(GraphParseError, match=(
        r'Illegal graph node.*'
    )):
        validate(id_)


def test_fail_cylc6_timeout_syntax(flow, validate):
    """Test validation with a new-style cycle point and a prev-style limit."""
    id_ = flow({
        'scheduling': {
            'initial cycle point': '20100101T00',
            'graph': {
                'T00,T06,T12': '"foo"',
            },
        },
        'runtime': {
            'root': {
                'events': {
                    'execution timeout': '3',
                },
            },
        },
    })
    with pytest.raises(IllegalValueError, match=(
        r'\(type=ISO 8601 interval\) \[runtime\]\[root\]\[events\].*'
    )):
        validate(id_)


def test_fail_cylc6_cycle_point(flow, validate):
    """Test validation with a prev-style cycle
    point and a new-style cycling section"""
    id_ = flow({
        'scheduling': {
            'initial cycle point': '2010010100',
            'graph': {
                'T12': '"foo"',
            },
        },
    })
    with pytest.raises(PointParsingError, match=(
        r'Incompatible value for.* Invalid ISO.*'
    )):
        validate(id_)


def test_fail_old_syntax_5(flow, validate):
    """Test validation with a new-style cycle point and start-up tasks."""
    id_ = flow({
        'scheduling': {
            'initial cycle point': '20100101T00',
            'special tasks': {
                'start-up': 'cold_foo',
            },
            'graph': {
                'T12': '"cold_foo => foo"',
            },
        },
    })
    with pytest.raises(IllegalItemError, match=(
        r'\[scheduling\]\[special tasks\]start-up.*'
    )):
        validate(id_)


def test_fail_old_syntax_6(flow, validate):
    """Test validation with a new-style cycle point and an async graph."""
    id_ = flow({
        'scheduling': {
            'initial cycle point': '20100101T00',
            'graph': {
                'R1': '"cold_foo"',
                '12': '"cold_foo => foo"',
            },
        },
    })
    with pytest.raises(WorkflowConfigError, match=(
        r'Cannot process recurrence.*'
    )):
        validate(id_)


def test_fail_no_scheduling(flow, validate):
    """Test validation with a new-style cycle point and an async graph."""
    id_ = flow({
    })
    with pytest.raises(WorkflowConfigError, match=(
        r'missing \[scheduling\] section.*'
    )):
        validate(id_)


def test_fail_empty_graph(flow, validate):
    """Test validation of an empty graph."""
    id_ = flow({
        'scheduling': {
            'graph': {
            },
        },
    })
    with pytest.raises(WorkflowConfigError, match=(
        r'No workflow dependency graph defined.*'
    )):
        validate(id_)


def test_fail_empty_graph_2(flow, validate):
    """Test validation of an empty graph."""
    id_ = flow({
        'scheduling': {
            'graph': {
                'R1': '""',
            },
        },
    })
    with pytest.raises(WorkflowConfigError, match=(
        r'No workflow dependency graph defined.'
    )):
        validate(id_)


def test_fail_no_graph(flow, validate):
    """Test validation fails if no graph is defined."""
    id_ = flow({
        'scheduling': {
            'initial cycle point': '2015',
            'graph': {
            },
        },
    })
    with pytest.raises(WorkflowConfigError, match=(
        r'No workflow dependency graph defined.'
    )):
        validate(id_)


def test_fail_year_bounds(flow, validate):
    """Test validation with a new-style cycle point and an async graph."""
    id_ = flow({
        'scheduling': {
            'initial cycle point': '+10000-01-01T00',
            'graph': {
                'T00': 'foo',
            },
        },
    })
    with pytest.raises(PointParsingError, match=(
        r'Incompatible value for.*'
    )):
        validate(id_)


def test_fail_initial_greater_final(flow, validate):
    """Test validation fails for initial cycle point greater than the final."""
    id_ = flow({
        'scheduler': {
            'UTC mode': 'True',
        },
        'scheduling': {
            'initial cycle point': '20141208T0000Z',
            'final cycle point': '20141207T0000Z',
            'graph': {
                'T00': 'A => B',
            },
        },
        'runtime': {
            'A': {
            },
            'B': {
            },
        },
    })
    with pytest.raises(WorkflowConfigError, match=(
        r'The initial cycle point.* is after the final cycle point.*'
    )):
        validate(id_)


def test_fail_constrained_intial(flow, validate):
    """Test validating simple multi-inheritance workflows."""
    id_ = flow({
        'scheduler': {
        },
        'scheduling': {
            'initial cycle point': '20100101T03',
            'initial cycle point constraints': 'T00, T06, T12, T18',
            'graph': {
                'T00, T06, T12, T18': 'foo',
            },
        },
        'runtime': {
            'FOO': {
            },
            'BAR': {
            },
            'foo': {
                'inherit': 'FOO, BAR',
            },
        },
    })
    with pytest.raises(WorkflowConfigError, match=(
        r'Initial cycle point .* does not meet the constraints.*'
    )):
        validate(id_)


def test_fail_constrained_final(flow, validate):
    """Test validating simple multi-inheritance workflows."""
    id_ = flow({
        'scheduler': {
        },
        'scheduling': {
            'initial cycle point': '20100101T03',
            'final cycle point': '20100102T17',
            'final cycle point constraints': 'T00, T06, T12, T18',
            'graph': {
                'T00, T06, T12, T18': '"""foo"""',
            },
        },
        'runtime': {
            'FOO': {
            },
            'BAR': {
            },
            'foo': {
                'inherit': 'FOO, BAR',
            },
        },
    })
    with pytest.raises(WorkflowConfigError, match=(
        r'Final cycle point .* does not meet the constraints.*'
    )):
        validate(id_)


def test_9999_rollover(flow, validate):
    """Test intercycle dependencies."""
    id_ = flow({
        'scheduler': {
            'UTC mode': 'True',
        },
        'scheduling': {
            'initial cycle point': '99991231T2200',
            'graph': {
                'R3//PT1H': '"foo"',
            },
        },
        'runtime': {
            'foo': {
                'script': 'true',
            },
        },
    })
    with pytest.raises(TimePointDumperBoundsError, match=(
        r'Cannot dump TimePoint year:.*'
    )):
        validate(id_)


def test_pass_constrained_initial(flow, validate):
    """Test validating simple multi-inheritance workflows."""
    id_ = flow({
        'scheduler': {
        },
        'scheduling': {
            'initial cycle point': '20100101T06',
            'initial cycle point constraints': 'T00, T06, T12, T18',
            'graph': {
                'T00, T06, T12, T18': '"""foo"""',
            },
        },
        'runtime': {
            'FOO': {
            },
            'BAR': {
            },
            'foo': {
                'inherit': 'FOO, BAR',
            },
        },
    })
    validate(id_)


def test_pass_constrained_final(flow, validate):
    """Test validating simple multi-inheritance workflows."""
    id_ = flow({
        'scheduler': {
        },
        'scheduling': {
            'initial cycle point': '20100101T06',
            'final cycle point': '20100101T18',
            'final cycle point constraints': 'T00, T06, T12, T18',
            'graph': {
                'T00, T06, T12, T18': '"""foo"""',
            },
        },
        'runtime': {
            'FOO': {
            },
            'BAR': {
            },
            'foo': {
                'inherit': 'FOO, BAR',
            },
        },
    })
    validate(id_)


def test_fail_not_integer(flow, validate):
    """Test validation with initial and final
    cycle points in scheduling but no R1."""
    id_ = flow({
        'scheduling': {
            'initial cycle point': '2015-01-01',
            'final cycle point': '2015-01-01',
            'graph': {
                '1': 'foo',
            },
        },
        'runtime': {
            'foo': {
                'script': 'sleep 10',
            },
        },
    })
    with pytest.raises(WorkflowConfigError, match=(
        r'Cannot process recurrence.*'
    )):
        validate(id_)


def test_no_clock_int_cycle(flow, validate):
    """Test validation fails when the cycle point format is
    less precise than a graph recurrence interval"""
    id_ = flow({
        'scheduler': {
            'cycle point format': '%Y-%m',
        },
        'scheduling': {
            'initial cycle point': '2015-08',
            'graph': {
                'P1D': 'foo',
            },
        },
    })
    with pytest.raises(SequenceDegenerateError, match=(
        r'R/2015-08/P1D, point format.*'
    )):
        validate(id_)


def test_hyphen_fam_1(flow, validate):
    """Test validation of task name with a XXX-FAM pattern."""
    id_ = flow({
        'scheduling': {
            'graph': {
                'R1': '"baz-foo => bar"',
            },
        },
        'runtime': {
            'foo': {
            },
            'bar, baz-foo': {
                'inherit': 'foo',
            },
        },
    })
    validate(id_)


def test_hyphen_fam_2(flow, validate):
    """Test validation of task name with a XXX-FAM pattern."""
    id_ = flow({
        'scheduling': {
            'graph': {
                'R1': '"foo-baz => bar"',
            },
        },
        'runtime': {
            'foo': {
            },
            'bar, foo-baz': {
                'inherit': 'foo',
            },
        },
    })
    validate(id_)


def test_null_timeout(flow, validate):
    """Test explicit unset timeout intervals validate (GitHub #1865)."""
    id_ = flow({
        'scheduling': {
            'graph': {
                'R1': 'foo',
            },
        },
        'runtime': {
            'foo': {
                'events': {
                    'execution timeout': '',
                },
            },
        },
    })
    validate(id_)


def test_hyphen_finish(flow, validate):
    """Test hyphen in task name + ":finish". See cylc/cylc-flow#1949."""
    id_ = flow({
        'scheduling': {
            'graph': {
                'R1': 'foo-bar:finish => baz',
            },
        },
        'runtime': {
            'foo-bar,baz': {
                'script': 'true',
            },
        },
    })
    validate(id_)


def test_succeed_sub(flow, validate):
    """In graph lines where we have multiple triggers
    of the same task, ensure:succeed does not get
    substituted to symbols that already have a trigger."""
    id_ = flow({
        'scheduling': {
            'graph': {
                'R1': 'foo:fail? | (foo? & bar:fail) => something',
            },
        },
        'runtime': {
            'root': {
                'script': 'true',
            },
        },
    })
    validate(id_)


def test_offset_no_offset(flow, validate):
    """GitHub PR #2002 - validation of "foo | foo[-P1D] => bar"
    was failing becausethe explicit ':succeed' trigger was being
    substituted before the offset instead of after, creating an
    invalid trigger expression."""
    id_ = flow({
        'scheduling': {
            'initial cycle point': '2010',
            'graph': {
                'P1D': 'foo | foo[-P1D] => bar',
            },
        },
    })
    validate(id_)


def test_icp_quoted_now(flow, validate):
    """Quoted "now" for initial cycle point was failing."""
    id_ = flow({
        'scheduler': {
            'cycle point format': '%Y%m%d',
        },
        'scheduling': {
            'initial cycle point': '"now"',
            'graph': {
                'P1D': 't1',
            },
        },
    })
    validate(id_)


def test_bad_task_event_handler_tmpl(flow, validate):
    """Test validation fails on bad task event handler templates."""
    id_ = flow({
        'scheduling': {
            'graph': {
                'R1': 't1',
            },
        },
        'runtime': {
            't1': {
                'script': 'true',
                'events': {
                    'failed handlers': 'echo %(id)s, echo %(rubbish)s',
                },
            },
        },
    })
    with pytest.raises(WorkflowConfigError, match=(
        r'bad task event handler template.*'
    )):
        validate(id_)


def test_no_clock_int_cycle_bad_value(flow, validate):
    """Test validation fails on bad task event handler templates."""
    id_ = flow({
        'scheduling': {
            'graph': {
                'R1': 't1',
            },
        },
        'runtime': {
            't1': {
                'events': {
                    'failed handlers': 'echo %(ids',
                },
            },
        },
    })
    with pytest.raises(WorkflowConfigError, match=(
        r'bad task event handler template.*'
    )):
        validate(id_)


def test_no_clock_int_cycle_xtrigger(flow, validate):
    """Test that clock xtriggers are not allowed with integer cycling."""
    id_ = flow({
        'scheduling': {
            'cycling mode': 'integer',
            'initial cycle point': '1',
            'final cycle point': '2',
            'xtriggers': {
                'c1': 'wall_clock(offset=P0Y)',
            },
            'graph': {
                'R/^/P1': '"@c1 & foo[-P1] => foo"',
            },
        },
    })
    with pytest.raises(WorkflowConfigError, match=(
        r'Clock xtriggers require datetime cycling.*'
    )):
        validate(id_)


def test_Valid_xtrigger_name(flow, validate):
    """Test validating xtrigger names in workflow."""
    id_ = flow({
        'scheduling': {
            'initial cycle point': '2000',
            'xtriggers': {
                'foo': 'wall_clock():PT1S',
            },
            'graph': {
                'R1': '@foo => bar',
            },
        },
    })
    validate(id_)


def test_Invalid_xtrigger_name(flow, validate):
    """Test validating xtrigger names in workflow."""
    id_ = flow({
        'scheduling': {
            'initial cycle point': '2000',
            'xtriggers': {
                'foo-1': 'wall_clock():PT1S',
            },
            'graph': {
                'R1': '@foo-1 => bar',
            },
        },
    })
    with pytest.raises(WorkflowConfigError, match=(
        r'Invalid xtrigger name.*'
    )):
        validate(id_)


def test_section_as_setting_normal(flow, validate):
    """Test handling of mixed up sections vs settings
    1. section as setting (normal)"""
    id_ = flow({
        'runtime': {
            'foo': {
                'environment': '42',
            },
        },
    })
    with pytest.raises(IllegalItemError, match=(
        r'\[runtime\]\[foo\]environment.*'
    )):
        validate(id_)


def test_section_as_setting_upgrader(flow, validate):
    """Test handling of mixed up sections vs settings
    2. section as setting (via upgrader)"""
    id_ = flow({
        'scheduling': '22',
    })
    with pytest.raises(UpgradeError, match=(
        r'\[scheduling\].*'
    )):
        validate(id_)


def test_setting_as_section(flow, validate):
    """Test handling of mixed up sections vs settings
    3. setting as section"""
    id_ = flow({
        'scheduling': {
            'initial cycle point': {
            },
        },
    })
    with pytest.raises(IllegalItemError, match=(
        r'\[scheduling\]initial cycle point.*'
    )):
        validate(id_)
