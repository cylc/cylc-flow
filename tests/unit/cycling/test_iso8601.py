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

from datetime import (
    datetime,
    timezone,
)

import pytest
from pytest import param

from cylc.flow.cycling.iso8601 import (
    ISO8601Interval,
    ISO8601Point,
    ISO8601Sequence,
    ingest_time,
)
from cylc.flow.cycling.loader import ISO8601_CYCLING_TYPE


def test_exclusions_simple(set_cycling_type):
    """Test the generation of points for sequences with exclusions."""
    set_cycling_type(ISO8601_CYCLING_TYPE, "Z")
    sequence = ISO8601Sequence("PT1H!20000101T02Z", "20000101T00Z")

    output = []
    point = sequence.get_start_point()
    count = 0
    while point and count < 4:
        output.append(point)
        point = sequence.get_next_point(point)
        count += 1
    output = [str(out) for out in output]
    assert output == [
        "20000101T0000Z",
        "20000101T0100Z",
        "20000101T0300Z",
        "20000101T0400Z",
    ]


def test_exclusions_offset(set_cycling_type):
    """Test the generation of points for sequences with exclusions
    that have an offset on the end"""
    set_cycling_type(ISO8601_CYCLING_TYPE, "Z")
    sequence = ISO8601Sequence("PT1H!20000101T00Z+PT1H", "20000101T00Z")

    output = []
    point = sequence.get_start_point()
    count = 0
    while point and count < 4:
        output.append(point)
        point = sequence.get_next_point(point)
        count += 1
    output = [str(out) for out in output]
    assert output == [
        "20000101T0000Z",
        "20000101T0200Z",
        "20000101T0300Z",
        "20000101T0400Z",
    ]


def test_multiple_exclusions_complex1(set_cycling_type):
    """Tests sequences that have multiple exclusions and a more
    complicated format"""
    set_cycling_type(ISO8601_CYCLING_TYPE, "Z")

    # A sequence that specifies a dep start time
    sequence = ISO8601Sequence(
        "20000101T01Z/PT1H!20000101T02Z", "20000101T01Z"
    )

    output = []
    point = sequence.get_start_point()
    count = 0
    # We are going to make four sequence points
    while point and count < 4:
        output.append(point)
        point = sequence.get_next_point(point)
        count += 1
    output = [str(out) for out in output]
    # We should expect one of the hours to be excluded: T02
    assert output == [
        "20000101T0100Z",
        "20000101T0300Z",
        "20000101T0400Z",
        "20000101T0500Z",
    ]


def test_multiple_exclusions_complex2(set_cycling_type):
    """Tests sequences that have multiple exclusions and a more
    complicated format"""
    set_cycling_type(ISO8601_CYCLING_TYPE, "Z")

    # A sequence that specifies a dep start time
    sequence = ISO8601Sequence(
        "20000101T01Z/PT1H!" "(20000101T02Z,20000101T03Z)",
        "20000101T00Z",
        "20000101T05Z",
    )

    output = []
    point = sequence.get_start_point()
    count = 0
    # We are going to make four sequence points
    while point and count < 3:
        output.append(point)
        point = sequence.get_next_point(point)
        count += 1
    output = [str(out) for out in output]
    # We should expect two of the hours to be excluded: T02, T03
    assert output == [
        "20000101T0100Z",
        "20000101T0400Z",
        "20000101T0500Z",
    ]


def test_multiple_exclusions_simple(set_cycling_type):
    """Tests generation of points for sequences with multiple exclusions"""
    set_cycling_type(ISO8601_CYCLING_TYPE, "Z")
    sequence = ISO8601Sequence(
        "PT1H!(20000101T02Z,20000101T03Z)", "20000101T00Z"
    )

    output = []
    point = sequence.get_start_point()
    count = 0
    # We are going to make four sequence points
    while point and count < 4:
        output.append(point)
        point = sequence.get_next_point(point)
        count += 1
    output = [str(out) for out in output]
    # We should expect two of the hours to be excluded: T02 and T03
    assert output == [
        "20000101T0000Z",
        "20000101T0100Z",
        "20000101T0400Z",
        "20000101T0500Z",
    ]


def test_advanced_exclusions_partial_datetime1(set_cycling_type):
    """Advanced exclusions refers to exclusions that are not just
    simple points but could be time periods or recurrences such as
    '!T06' or similar"""
    set_cycling_type(ISO8601_CYCLING_TYPE, "Z")
    # Run 3-hourly but not at 06:00 (from the ICP)
    sequence = ISO8601Sequence("PT3H!T06", "20000101T00Z")

    output = []
    point = sequence.get_start_point()
    count = 0
    # We are going to make ten sequence points
    while point and count < 10:
        output.append(point)
        point = sequence.get_next_point(point)
        count += 1
    output = [str(out) for out in output]
    # We should expect every T06 to be excluded
    assert output == [
        "20000101T0000Z",
        "20000101T0300Z",
        "20000101T0900Z",
        "20000101T1200Z",
        "20000101T1500Z",
        "20000101T1800Z",
        "20000101T2100Z",
        "20000102T0000Z",
        "20000102T0300Z",
        "20000102T0900Z",
    ]


def test_advanced_exclusions_partial_datetime2(set_cycling_type):
    """Advanced exclusions refers to exclusions that are not just
    simple points but could be time periods or recurrences such as
    '!T06' or similar"""
    set_cycling_type(ISO8601_CYCLING_TYPE, "Z")
    # Run hourly but not at 00:00, 06:00, 12:00, 18:00
    sequence = ISO8601Sequence("T-00!(T00, T06, T12, T18)", "20000101T00Z")

    output = []
    point = sequence.get_start_point()
    count = 0
    # We are going to make 18 sequence points
    while point and count < 18:
        output.append(point)
        point = sequence.get_next_point(point)
        count += 1
    output = [str(out) for out in output]
    # We should expect T00, T06, T12, and T18 to be excluded
    assert output == [
        "20000101T0100Z",
        "20000101T0200Z",
        "20000101T0300Z",
        "20000101T0400Z",
        "20000101T0500Z",
        "20000101T0700Z",
        "20000101T0800Z",
        "20000101T0900Z",
        "20000101T1000Z",
        "20000101T1100Z",
        "20000101T1300Z",
        "20000101T1400Z",
        "20000101T1500Z",
        "20000101T1600Z",
        "20000101T1700Z",
        "20000101T1900Z",
        "20000101T2000Z",
        "20000101T2100Z",
    ]


def test_advanced_exclusions_partial_datetime3(set_cycling_type):
    """Advanced exclusions refers to exclusions that are not just
    simple points but could be time periods or recurrences such as
    '!T06' or similar"""
    set_cycling_type(ISO8601_CYCLING_TYPE, "Z")
    # Run 5 minutely but not at 15 minutes past the hour from ICP
    sequence = ISO8601Sequence("PT5M!T-15", "20000101T00Z")

    output = []
    point = sequence.get_start_point()
    count = 0
    # We are going to make 15 sequence points
    while point and count < 15:
        output.append(point)
        point = sequence.get_next_point(point)
        count += 1
    output = [str(out) for out in output]
    # We should expect xx:15 (15 minutes past the hour) to be excluded
    assert output == [
        "20000101T0000Z",
        "20000101T0005Z",
        "20000101T0010Z",
        "20000101T0020Z",
        "20000101T0025Z",
        "20000101T0030Z",
        "20000101T0035Z",
        "20000101T0040Z",
        "20000101T0045Z",
        "20000101T0050Z",
        "20000101T0055Z",
        "20000101T0100Z",
        "20000101T0105Z",
        "20000101T0110Z",
        "20000101T0120Z",
    ]


def test_advanced_exclusions_partial_datetime4(set_cycling_type):
    """Advanced exclusions refers to exclusions that are not just
    simple points but could be time periods or recurrences such as
    '!T06' or similar"""
    set_cycling_type(ISO8601_CYCLING_TYPE, "Z")
    # Run daily at 00:00 except on Mondays
    sequence = ISO8601Sequence("T00!W-1T00", "20170422T00Z")

    output = []
    point = sequence.get_start_point()
    count = 0
    # We are going to make 19 sequence points
    while point and count < 9:
        output.append(point)
        point = sequence.get_next_point(point)
        count += 1
    output = [str(out) for out in output]
    # We should expect Monday 24th April and Monday 1st May
    # to be excluded.
    assert output == [
        "20170422T0000Z",
        "20170423T0000Z",
        "20170425T0000Z",
        "20170426T0000Z",
        "20170427T0000Z",
        "20170428T0000Z",
        "20170429T0000Z",
        "20170430T0000Z",
        "20170502T0000Z",
    ]


def test_exclusions_to_string(set_cycling_type):
    set_cycling_type(ISO8601_CYCLING_TYPE, "Z")
    # Check that exclusions are not included where they should not be.
    basic = ISO8601Sequence("PT1H", "2000", "2001")
    assert "!" not in str(basic)

    # Check that exclusions are parsable.
    sequence = ISO8601Sequence("PT1H!(20000101T10Z, PT6H)", "2000", "2001")
    sequence2 = ISO8601Sequence(str(sequence), "2000", "2001")
    assert sequence == sequence2


def test_advanced_exclusions_sequences1(set_cycling_type):
    """Advanced exclusions refers to exclusions that are not just
    simple points but could be time periods or recurrences such as
    '!T06' or similar"""
    set_cycling_type(ISO8601_CYCLING_TYPE, "Z")
    # Run hourly from the ICP but not 3-hourly
    sequence = ISO8601Sequence("PT1H!PT3H", "20000101T01Z")

    output = []
    point = sequence.get_start_point()
    count = 0
    # We are going to make six sequence points
    while point and count < 6:
        output.append(point)
        point = sequence.get_next_point(point)
        count += 1
    output = [str(out) for out in output]
    # We should expect to see hourly from ICP but not 3 hourly
    assert output == [
        "20000101T0200Z",
        "20000101T0300Z",
        "20000101T0500Z",
        "20000101T0600Z",
        "20000101T0800Z",
        "20000101T0900Z",
    ]


def test_advanced_exclusions_sequences2(set_cycling_type):
    """Advanced exclusions refers to exclusions that are not just
    simple points but could be time periods or recurrences such as
    '!T06' or similar"""
    set_cycling_type(ISO8601_CYCLING_TYPE, "Z")
    # Run hourly on the hour but not 3 hourly on the hour
    sequence = ISO8601Sequence("T-00!T-00/PT3H", "20000101T00Z")

    output = []
    point = sequence.get_start_point()
    count = 0
    # We are going to make six sequence points
    while point and count < 6:
        output.append(point)
        point = sequence.get_next_point(point)
        count += 1
    output = [str(out) for out in output]

    assert output == [
        "20000101T0100Z",
        "20000101T0200Z",
        "20000101T0400Z",
        "20000101T0500Z",
        "20000101T0700Z",
        "20000101T0800Z",
    ]


def test_advanced_exclusions_sequences3(set_cycling_type):
    """Advanced exclusions refers to exclusions that are not just
    simple points but could be time periods or recurrences such as
    '!T06' or similar"""
    set_cycling_type(ISO8601_CYCLING_TYPE, "Z")
    # Run daily at 12:00 except every 3rd day
    sequence = ISO8601Sequence("T12!P3D", "20000101T12Z")

    output = []
    point = sequence.get_start_point()
    count = 0
    # We are going to make six sequence points
    while point and count < 6:
        output.append(point)
        point = sequence.get_next_point(point)
        count += 1
    output = [str(out) for out in output]

    assert output == [
        "20000102T1200Z",
        "20000103T1200Z",
        "20000105T1200Z",
        "20000106T1200Z",
        "20000108T1200Z",
        "20000109T1200Z",
    ]


def test_advanced_exclusions_sequences4(set_cycling_type):
    """Advanced exclusions refers to exclusions that are not just
    simple points but could be time periods or recurrences such as
    '!T06' or similar"""
    set_cycling_type(ISO8601_CYCLING_TYPE, "Z")
    # Run every hour from 01:00 excluding every 3rd hour.
    sequence = ISO8601Sequence("T01/PT1H!+PT3H/PT3H", "20000101T01Z")

    output = []
    point = sequence.get_start_point()
    count = 0
    # We are going to make six sequence points
    while point and count < 6:
        output.append(point)
        point = sequence.get_next_point(point)
        count += 1
    output = [str(out) for out in output]

    assert output == [
        "20000101T0100Z",
        "20000101T0200Z",
        "20000101T0300Z",
        "20000101T0500Z",
        "20000101T0600Z",
        "20000101T0800Z",
    ]


def test_advanced_exclusions_sequences5(set_cycling_type):
    """Advanced exclusions refers to exclusions that are not just
    simple points but could be time periods or recurrences such as
    '!T06' or similar"""
    set_cycling_type(ISO8601_CYCLING_TYPE, "Z")
    # Run every hour from 01:00 excluding every 3rd hour.
    sequence = ISO8601Sequence("T-00 ! 2000", "20000101T00Z")

    output = []
    point = sequence.get_start_point()
    count = 0
    # We are going to make six sequence points
    while point and count < 6:
        output.append(point)
        point = sequence.get_next_point(point)
        count += 1
    output = [str(out) for out in output]

    assert output == [
        "20000101T0100Z",
        "20000101T0200Z",
        "20000101T0300Z",
        "20000101T0400Z",
        "20000101T0500Z",
        "20000101T0600Z",
    ]


def test_advanced_exclusions_sequences_mix_points_sequences(set_cycling_type):
    """Advanced exclusions refers to exclusions that are not just
    simple points but could be time periods or recurrences such as
    '!T06' or similar"""
    set_cycling_type(ISO8601_CYCLING_TYPE, "Z")
    # Run every hour from 01:00 excluding every 3rd hour.
    sequence = ISO8601Sequence("T-00 ! (2000, PT2H)", "20000101T00Z")

    output = []
    point = sequence.get_start_point()
    count = 0
    # We are going to make six sequence points
    while point and count < 6:
        output.append(point)
        point = sequence.get_next_point(point)
        count += 1
    output = [str(out) for out in output]

    assert output == [
        "20000101T0100Z",
        "20000101T0300Z",
        "20000101T0500Z",
        "20000101T0700Z",
        "20000101T0900Z",
        "20000101T1100Z",
    ]


def test_advanced_exclusions_sequences_implied_start_point(set_cycling_type):
    """Advanced exclusions refers to exclusions that are not just
    simple points but could be time periods or recurrences such as
    '!T06' or similar"""
    set_cycling_type(ISO8601_CYCLING_TYPE, "Z")
    # Run every hour from 01:00 excluding every 3rd hour.
    sequence = ISO8601Sequence("T05/PT1H!PT3H", "20000101T00Z")

    output = []
    point = sequence.get_start_point()
    count = 0
    # We are going to make six sequence points
    while point and count < 6:
        output.append(point)
        point = sequence.get_next_point(point)
        count += 1
    output = [str(out) for out in output]

    assert output == [
        "20000101T0600Z",
        "20000101T0700Z",
        "20000101T0900Z",
        "20000101T1000Z",
        "20000101T1200Z",
        "20000101T1300Z",
    ]


def test_point_init():
    """It should error if inited with anything other than a string."""
    ISO8601Point('1000')
    with pytest.raises(TypeError):
        ISO8601Point(1000)
    with pytest.raises(TypeError):
        ISO8601Interval(1000)


def test_exclusions_sequences_points(set_cycling_type):
    """Test ISO8601Sequence methods for sequences with exclusions"""
    set_cycling_type(ISO8601_CYCLING_TYPE, "Z")
    # Run every hour from 01:00 excluding every 3rd hour
    sequence = ISO8601Sequence("T01/PT1H!PT3H", "20000101T01Z")

    point_0 = ISO8601Point("20000101T00Z")
    point_1 = ISO8601Point("20000101T01Z")
    point_2 = ISO8601Point("20000101T02Z")
    point_3 = ISO8601Point("20000101T03Z")
    point_4 = ISO8601Point("20000101T04Z")

    assert point_0 not in sequence.exclusions
    assert point_1 in sequence.exclusions
    assert sequence.is_on_sequence(point_2)
    assert sequence.is_on_sequence(point_3)
    assert not sequence.is_on_sequence(point_4)
    assert point_4 in sequence.exclusions


def test_exclusions_extensive(set_cycling_type):
    """Test ISO8601Sequence methods for sequences with exclusions"""
    set_cycling_type(ISO8601_CYCLING_TYPE, "+05")
    sequence = ISO8601Sequence(
        "PT1H!20000101T02+05", "20000101T00", "20000101T05"
    )

    point_0 = ISO8601Point("20000101T0000+05")
    point_1 = ISO8601Point("20000101T0100+05")
    point_2 = ISO8601Point("20000101T0200+05")  # The excluded point.
    point_3 = ISO8601Point("20000101T0300+05")

    assert not sequence.is_on_sequence(point_2)
    assert not sequence.is_valid(point_2)
    assert sequence.get_prev_point(point_2) == point_1
    assert sequence.get_prev_point(point_3) == point_1
    assert sequence.get_prev_point(point_2) == point_1
    assert sequence.get_nearest_prev_point(point_3) == point_1
    assert sequence.get_next_point(point_1) == point_3
    assert sequence.get_next_point(point_2) == point_3

    sequence = ISO8601Sequence("PT1H!20000101T00+05", "20000101T00+05")
    assert sequence.get_first_point(point_0) == point_1
    assert sequence.get_start_point() == point_1


def test_multiple_exclusions_extensive(set_cycling_type):
    """Test ISO8601Sequence methods for sequences with multiple exclusions"""
    set_cycling_type(ISO8601_CYCLING_TYPE, "+05")
    sequence = ISO8601Sequence(
        "PT1H!(20000101T02,20000101T03)", "20000101T00", "20000101T06"
    )

    point_0 = ISO8601Point("20000101T0000+05")
    point_1 = ISO8601Point("20000101T0100+05")
    point_2 = ISO8601Point("20000101T0200+05")  # First excluded point
    point_3 = ISO8601Point("20000101T0300+05")  # Second excluded point
    point_4 = ISO8601Point("20000101T0400+05")

    # Check the excluded points are not on the sequence
    assert not sequence.is_on_sequence(point_2)
    assert not sequence.is_on_sequence(point_3)
    assert not sequence.is_valid(point_2)  # Should be excluded
    assert not sequence.is_valid(point_3)  # Should be excluded
    # Check that we can correctly retrieve previous points
    assert sequence.get_prev_point(point_2) == point_1
    # Should skip two excluded points
    assert sequence.get_prev_point(point_4) == point_1
    assert sequence.get_prev_point(point_2) == point_1
    assert sequence.get_nearest_prev_point(point_4) == point_1
    assert sequence.get_next_point(point_1) == point_4
    assert sequence.get_next_point(point_3) == point_4

    sequence = ISO8601Sequence("PT1H!20000101T00+05", "20000101T00")
    # Check that the first point is after 00.
    assert sequence.get_first_point(point_0) == point_1
    assert sequence.get_start_point() == point_1

    # Check a longer list of exclusions
    # Also note you can change the format of the exclusion list
    # (removing the parentheses)
    sequence = ISO8601Sequence(
        "PT1H!(20000101T02+05, 20000101T03+05," "20000101T04+05)",
        "20000101T00",
        "20000101T06",
    )
    assert sequence.get_prev_point(point_3) == point_1
    assert sequence.get_prev_point(point_4) == point_1


def test_exclusion_zero_duration_warning(set_cycling_type, caplog, log_filter):
    """It should not log zero-duration warnings for exclusion points.

    Exclusions may either be sequences or points. We first attempt to parse
    them as sequences, if this fails, we attempt to parse them as points.

    The zero-duration recurrence warning would be logged if we attempted to
    parse a point as a sequence. To avoid spurious warnings this should be
    turned off for exclusion parsing.

    """
    # parsing a point as a sequences causes a zero-duration warning
    set_cycling_type(ISO8601_CYCLING_TYPE, "+05")
    with pytest.raises(Exception):
        ISO8601Sequence('3000', '2999')
    assert log_filter(contains='zero-duration')

    # parsing a point in an exclusion should not
    caplog.clear()
    ISO8601Sequence('P1Y ! 3000', '2999')
    assert not log_filter(contains='zero-duration')


def test_simple(set_cycling_type):
    """Run some simple tests for date-time cycling."""
    set_cycling_type(ISO8601_CYCLING_TYPE, "Z")
    p_start = ISO8601Point("20100808T00")
    p_stop = ISO8601Point("20100808T02")
    i = ISO8601Interval("PT6H")
    assert p_start - i == ISO8601Point("20100807T18")
    assert p_stop + i == ISO8601Point("20100808T08")

    sequence = ISO8601Sequence(
        "PT10M",
        str(p_start),
        str(p_stop),
    )
    sequence.set_offset(-ISO8601Interval("PT10M"))
    point = sequence.get_next_point(ISO8601Point("20100808T0000"))
    assert point == ISO8601Point("20100808T0010")
    output = []

    # Test point generation forwards.
    while point and point < p_stop:
        output.append(point)
        assert sequence.is_on_sequence(point)
        point = sequence.get_next_point(point)
    assert [str(out) for out in output] == [
        "20100808T0010Z",
        "20100808T0020Z",
        "20100808T0030Z",
        "20100808T0040Z",
        "20100808T0050Z",
        "20100808T0100Z",
        "20100808T0110Z",
        "20100808T0120Z",
        "20100808T0130Z",
        "20100808T0140Z",
        "20100808T0150Z",
    ]

    assert point == ISO8601Point("20100808T0200")

    # Test point generation backwards.
    output = []
    while point and point >= p_start:
        output.append(point)
        assert sequence.is_on_sequence(point)
        point = sequence.get_prev_point(point)
    assert [str(out) for out in output] == [
        "20100808T0200Z",
        "20100808T0150Z",
        "20100808T0140Z",
        "20100808T0130Z",
        "20100808T0120Z",
        "20100808T0110Z",
        "20100808T0100Z",
        "20100808T0050Z",
        "20100808T0040Z",
        "20100808T0030Z",
        "20100808T0020Z",
        "20100808T0010Z",
        "20100808T0000Z",
    ]
    assert not sequence.is_on_sequence(ISO8601Point("20100809T0005"))


@pytest.mark.parametrize(
    'value, expected', [
        ('next(T2100Z)', '20100808T2100Z'),
        ('next(T00)', '20100809T0000Z'),
        ('next(T-15)', '20100808T1615Z'),
        ('next(T-45)', '20100808T1545Z'),
        ('next(-10)', '21100101T0000Z'),
        ('next(-1008)', '21100801T0000Z'),
        ('next(--10)', '20101001T0000Z'),
        ('next(--0325)', '20110325T0000Z'),
        ('next(---10)', '20100810T0000Z'),
        ('next(---05T1200Z)', '20100905T1200Z'),
        param('next(--08-08)', '20110808T0000Z', marks=pytest.mark.xfail),
        ('next(T15)', '20100809T1500Z'),
        ('next(T-41)', '20100808T1541Z'),
    ]
)
def test_next_simple(value: str, expected: str, set_cycling_type):
    """Test the generation of CP using 'next' from single input."""
    set_cycling_type(ISO8601_CYCLING_TYPE, "Z")
    my_now = "2010-08-08T15:41Z"
    assert ingest_time(value, my_now) == expected


@pytest.mark.parametrize(
    'value, expected', [
        ('previous(T2100Z)', '20100807T2100Z'),
        ('previous(T00)', '20100808T0000Z'),
        ('previous(T-15)', '20100808T1515Z'),
        ('previous(T-45)', '20100808T1445Z'),
        ('previous(-10)', '20100101T0000Z'),
        ('previous(-1008)', '20100801T0000Z'),
        ('previous(--10)', '20091001T0000Z'),
        ('previous(--0325)', '20100325T0000Z'),
        ('previous(---10)', '20100710T0000Z'),
        ('previous(---05T1200Z)', '20100805T1200Z'),
        param('previous(--08-08)', '20100808T0000Z', marks=pytest.mark.xfail),
        ('previous(T15)', '20100808T1500Z'),
        ('previous(T-41)', '20100808T1441Z'),
    ]
)
def test_previous_simple(value: str, expected: str, set_cycling_type):
    """Test the generation of CP using 'previous' from single input."""
    set_cycling_type(ISO8601_CYCLING_TYPE, "Z")
    my_now = "2010-08-08T15:41Z"
    assert ingest_time(value, my_now) == expected


def test_sequence(set_cycling_type):
    """Test the generation of CP from list input."""
    set_cycling_type(ISO8601_CYCLING_TYPE, "Z")
    my_now = "20100808T1540Z"
    sequence = (
        "next(T-00;T-15;T-30;T-45)",  # 20100808T1545Z
        "previous(T-00;T-15;T-30;T-45)",  # 20100808T1530Z
        "next(T00;T06;T12;T18)",  # 20100808T1800Z
        "previous(T00;T06;T12;T18)",
    )  # 20100808T1200Z

    output = []

    for point in sequence:
        output.append(ingest_time(point, my_now))
    assert output == [
        "20100808T1545Z",
        "20100808T1530Z",
        "20100808T1800Z",
        "20100808T1200Z",
    ]


def test_offset_simple(set_cycling_type):
    """Test the generation of offset CP."""
    set_cycling_type(ISO8601_CYCLING_TYPE, "Z")
    my_now = "20100808T1540Z"
    sequence = (
        "PT15M",    # 20100808T1555Z
        "-PT30M",   # 20100808T1510Z
        "PT1H",     # 20100808T1640Z
        "-PT18H",   # 20100807T2140Z
        "P3D",      # 20100811T1540Z
        "-P2W",     # 20100725T1540Z
        "P6M",      # 20110208T1540Z
        "-P1M",     # 20100708T1540Z
        "P1Y",      # 20110808T1540Z
        "-P5Y",     # 20050808T1540Z
    )

    output = []

    for point in sequence:
        output.append(ingest_time(point, my_now))
    assert output == [
        "20100808T1555Z",
        "20100808T1510Z",
        "20100808T1640Z",
        "20100807T2140Z",
        "20100811T1540Z",
        "20100725T1540Z",
        "20110208T1540Z",
        "20100708T1540Z",
        "20110808T1540Z",
        "20050808T1540Z",
    ]


def test_offset(set_cycling_type):
    """Test the generation of offset CP with 'next' and 'previous'."""
    set_cycling_type(ISO8601_CYCLING_TYPE, "Z")
    my_now = "20100808T1540Z"
    sequence = (
        "next(T06) +P1D",                   # 20100810T0600Z
        "previous(T-30) -PT12H",            # 20100808T0330Z
        "next(T00;T06;T12;T18) -P1W",       # 20100801T1800Z
        "previous(T00;T06;T12;T18) +PT1H",  # 20100808T1300Z
    )

    output = []

    for point in sequence:
        output.append(ingest_time(point, my_now))
    assert output == [
        "20100810T0600Z",
        "20100808T0330Z",
        "20100801T1800Z",
        "20100808T1300Z",
    ]


def test_weeks_days(set_cycling_type):
    """Test the generation of CP with day-of-week,
    ordinal day, and week (with day-of-week specified)."""
    set_cycling_type(ISO8601_CYCLING_TYPE, "Z")
    my_now = "20100808T1540Z"
    sequence = (
        "next(-W-1)",        # 20100809T0000Z
        "previous(-W-4)",    # 20100805T0000Z
        "next(-010)",        # 20110110T0000Z
        "previous(-101)",    # 20100411T0000Z
        "next(-W40-1)",      # 20101004T0000Z
        "previous(-W05-1)",  # 20100201T0000Z
        "next(-W05-5)",      # 20110204T0000Z
        "previous(-W40-4)",  # 20091001T0000Z
    )

    output = []

    for point in sequence:
        output.append(ingest_time(point, my_now))
    assert output == [
        "20100809T0000Z",
        "20100805T0000Z",
        "20110110T0000Z",
        "20100411T0000Z",
        "20101004T0000Z",
        "20100201T0000Z",
        "20110204T0000Z",
        "20091001T0000Z",
    ]


@pytest.mark.parametrize(
    'value, expected', [
        ('next(T-00)', '20180314T1600Z'),
        ('previous(T-00)', '20180314T1500Z'),
        ('next(T-00; T-15; T-30; T-45)', '20180314T1515Z'),
        ('previous(T-00; T-15; T-30; T-45)', '20180314T1500Z'),
        ('next(T00)', '20180315T0000Z'),
        ('previous(T00)', '20180314T0000Z'),
        ('next(T06:30Z)', '20180315T0630Z'),
        ('previous(T06:30) -P1D', '20180313T0630Z'),
        ('next(T00; T06; T12; T18)', '20180314T1800Z'),
        ('previous(T00; T06; T12; T18)', '20180314T1200Z'),
        ('next(T00; T06; T12; T18)+P1W', '20180321T1800Z'),
        ('PT1H', '20180314T1612Z'),
        ('-P1M', '20180214T1512Z'),
        ('next(-00)', '21000101T0000Z'),
        ('previous(--01)', '20180101T0000Z'),
        ('next(---01)', '20180401T0000Z'),
        ('previous(--1225)', '20171225T0000Z'),
        ('next(-2006)', '20200601T0000Z'),
        ('previous(-W101)', '20180305T0000Z'),
        ('next(-W-1; -W-3; -W-5)', '20180314T0000Z'),
        ('next(-001; -091; -181; -271)', '20180401T0000Z'),
        ('previous(-365T12Z)', '20171231T1200Z'),
    ]
)
def test_user_guide_examples(value: str, expected: str, set_cycling_type):
    """Test the offset CP examples in the Cylc user guide.

    https://cylc.github.io/cylc-doc/stable/html/user-guide/writing-workflows/scheduling.html
    """
    set_cycling_type(ISO8601_CYCLING_TYPE, "Z")
    my_now = "2018-03-14T15:12Z"
    assert ingest_time(value, my_now) == expected


def test_next_simple_no_now(set_cycling_type):
    """Test the generation of CP using 'next' with no value for `now`."""
    set_cycling_type(ISO8601_CYCLING_TYPE, "Z")
    my_now = None
    point = "next(T00Z)+P1D"
    output = ingest_time(point, my_now)

    current_time = datetime.now(timezone.utc)
    # my_now is None, but ingest_time will have used a similar time, and
    # the returned value must be after current_time
    output_time = datetime.strptime(output, "%Y%m%dT%H%M%z")
    assert current_time < output_time


def test_integer_cycling_is_returned(set_cycling_type):
    """Test that when integer points are given, the same value is
    returned."""
    set_cycling_type(ISO8601_CYCLING_TYPE, "Z")
    integer_point = "1"
    assert integer_point, ingest_time(integer_point is None)


def test_expanded_dates_are_returned(set_cycling_type):
    """Test that when expanded dates are given, the same value is
    returned."""
    set_cycling_type(ISO8601_CYCLING_TYPE, "Z")
    expanded_date = "+0100400101T0000Z"
    assert expanded_date, ingest_time(expanded_date is None)


def test_timepoint_truncated(set_cycling_type):
    """Test that when a timepoint is given, and is truncated, then the
    value is added to `now`."""
    set_cycling_type(ISO8601_CYCLING_TYPE, "Z")
    my_now = "2018-03-14T15:12Z"
    timepoint_truncated = "T15:00Z"  # 20180315T1500Z
    output = ingest_time(timepoint_truncated, my_now)
    assert output == "20180315T1500Z"


def test_timepoint(set_cycling_type):
    """Test that when a timepoint is given, and is not truncated, the
    same value is returned."""
    set_cycling_type(ISO8601_CYCLING_TYPE, "Z")
    my_now = "2018-03-14T15:12Z"
    timepoint_truncated = "19951231T0630"  # 19951231T0630
    output = ingest_time(timepoint_truncated, my_now)
    assert output == "19951231T0630"


@pytest.mark.parametrize(
    "_input, errortext",
    (
        ("next (T-00, T-30)", "T-00;T-30"),
        ("next (wildebeest)", "Invalid ISO 8601 date"),
    ),
)
def test_validate_fails_comma_sep_offset_list(
    _input, errortext, set_cycling_type
):
    """It raises an exception if validating a list separated by commas"""
    set_cycling_type(ISO8601_CYCLING_TYPE, "Z")
    with pytest.raises(Exception, match=errortext):
        ingest_time(_input)
