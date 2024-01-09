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

async def test_360_calendar(flow, scheduler, reftest):
    """Test 360 day calendar."""
    wid = flow({
        'scheduling': {
            'initial cycle point': '2013-02-28',
            'final cycle point': '2013-03-01',
            'cycling mode': '360day',
            'graph': {
                'P1D': 'foo[-P1D] => foo'
            },
        },
    })
    schd = scheduler(wid, paused_start=False)

    assert await reftest(schd) == {
        ('20130228T0000Z/foo', ('20130227T0000Z/foo',)),
        ('20130229T0000Z/foo', ('20130228T0000Z/foo',)),
        ('20130230T0000Z/foo', ('20130229T0000Z/foo',)),
        ('20130301T0000Z/foo', ('20130230T0000Z/foo',)),
    }


async def test_365_calendar(flow, scheduler, reftest):
    """Test 365 day calendar."""
    wid = flow({
        'scheduling': {
            'initial cycle point': '2012-02-28',
            'final cycle point': '2012-03-01',
            'cycling mode': '365day',
            'graph': {
                'P1D': 'foo[-P1D] => foo'
            },
        },
    })
    schd = scheduler(wid, paused_start=False)

    assert await reftest(schd) == {
        ('20120228T0000Z/foo', ('20120227T0000Z/foo',)),
        ('20120301T0000Z/foo', ('20120228T0000Z/foo',)),
    }


async def test_366_calendar(flow, scheduler, reftest):
    """Test 366 day calendar."""
    wid = flow({
        'scheduling': {
            'initial cycle point': '2013-02-28',
            'final cycle point': '2013-03-01',
            'cycling mode': '366day',
            'graph': {
                'P1D': 'foo[-P1D] => foo'
            },
        },
    })
    schd = scheduler(wid, paused_start=False)

    assert await reftest(schd) == {
        ('20130228T0000Z/foo', ('20130227T0000Z/foo',)),
        ('20130229T0000Z/foo', ('20130228T0000Z/foo',)),
        ('20130301T0000Z/foo', ('20130229T0000Z/foo',)),
    }


async def test_icp_fcp_notation(flow, scheduler, reftest):
    """Test initial and final cycle point special notation (^, $)"""
    wid = flow({
        'scheduling': {
            'initial cycle point': '2016-01-01',
            'final cycle point': '2016-01-02',
            'graph': {
                'R1': 'foo',
                'R1/^': 'bar',
                'R1/^+PT1H': 'baz',
                'R1/$-PT1H': 'boo',
                'R1/$': 'foo[^] & bar[^] & baz[^+PT1H] & boo[^+PT23H] => bot'
            },
        },
    })
    schd = scheduler(wid, paused_start=False)

    assert await reftest(schd) == {
        ('20160101T0000Z/foo', None),
        ('20160101T0000Z/bar', None),
        ('20160101T0100Z/baz', None),
        ('20160101T2300Z/boo', None),
        ('20160102T0000Z/bot', ('20160101T0000Z/bar', '20160101T0000Z/foo', '20160101T0100Z/baz', '20160101T2300Z/boo')),
    }


async def test_recurrence_format_1(flow, scheduler, reftest):
    """Test ISO 8601 recurrence format no. 1 with unbounded repetitions."""
    wid = flow({
        'scheduler': {
            'cycle point format': 'CCYY-MM-DD',
        },
        'scheduling': {
            'initial cycle point': '2010-01-01',
            'final cycle point': '2010-01-10',
            'graph': {
                'R/2010-01-01/2010-01-04': 'worf',  # 3-day interval
            },
        },
    })
    schd = scheduler(wid, paused_start=False)

    assert await reftest(schd) == {
        ('2010-01-01/worf', None),
        ('2010-01-04/worf', None),
        ('2010-01-07/worf', None),
        ('2010-01-10/worf', None),
    }
