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

async def test_basic(flow, scheduler, reftest):
    """Test simplification of basic conditionals in pre-initial cycling"""
    wid = flow({
        'scheduling': {
            'initial cycle point': '2010-01-01',
            'final cycle point': '2010-01-02',
            'graph': {
                'T00': 'a[-P1D] & b => a',
            },
        },
    })
    schd = scheduler(wid, paused_start=False)

    # 20100101T0000Z/b -triggered off []
    # 20100102T0000Z/b -triggered off []
    # 20100101T0000Z/a -triggered off ['20091231T0000Z/a', '20100101T0000Z/b']
    # 20100102T0000Z/a -triggered off ['20100101T0000Z/a', '20100102T0000Z/b']
    assert await reftest(schd) == {
        ('20100101T0000Z/b', None),
        ('20100102T0000Z/b', None),
        ('20100101T0000Z/a', ('20091231T0000Z/a', '20100101T0000Z/b')),
        ('20100102T0000Z/a', ('20100101T0000Z/a', '20100102T0000Z/b')),
    }


async def test_advanced(flow, scheduler, reftest):
    """Test nested conditional simplification for pre-initial cycling."""
    wid = flow({
        'scheduling': {
            'initial cycle point': '2010-01-01',
            'final cycle point': '2010-01-02',
            'graph': {
                'PT6H': '(a[-PT6H] & b) & c[-PT6H] => a & c',
            },
        },
    })
    schd = scheduler(wid, paused_start=False)

    assert await reftest(schd) == {
        ('20100101T0000Z/b', None),
        ('20100101T0600Z/b', None),
        ('20100101T0000Z/a', ('20091231T1800Z/a', '20091231T1800Z/c', '20100101T0000Z/b')),
        ('20100101T0000Z/c', ('20091231T1800Z/a', '20091231T1800Z/c', '20100101T0000Z/b')),
        ('20100101T1200Z/b', None),
        ('20100101T0600Z/a', ('20100101T0000Z/a', '20100101T0000Z/c', '20100101T0600Z/b')),
        ('20100101T0600Z/c', ('20100101T0000Z/a', '20100101T0000Z/c', '20100101T0600Z/b')),
        ('20100101T1800Z/b', None),
        ('20100101T1200Z/a', ('20100101T0600Z/a', '20100101T0600Z/c', '20100101T1200Z/b')),
        ('20100101T1200Z/c', ('20100101T0600Z/a', '20100101T0600Z/c', '20100101T1200Z/b')),
        ('20100102T0000Z/b', None),
        ('20100101T1800Z/c', ('20100101T1200Z/a', '20100101T1200Z/c', '20100101T1800Z/b')),
        ('20100101T1800Z/a', ('20100101T1200Z/a', '20100101T1200Z/c', '20100101T1800Z/b')),
        ('20100102T0000Z/a', ('20100101T1800Z/a', '20100101T1800Z/c', '20100102T0000Z/b')),
        ('20100102T0000Z/c', ('20100101T1800Z/a', '20100101T1800Z/c', '20100102T0000Z/b')),
    }


async def test_drop(flow, scheduler, reftest):
    """Test the case of dropping a conditional based on pre-initial cycling"""
    wid = flow({
        'scheduling': {
            'initial cycle point': '2010-01-01',
            'final cycle point': '2010-01-02',
            'graph': {
                'PT6H': 'a[-PT6H] & b[-PT6H] => a => b',
            },
        },
    })
    schd = scheduler(wid, paused_start=False)

    assert await reftest(schd) == {
        ('20100101T0000Z/a', ('20091231T1800Z/a', '20091231T1800Z/b')),
        ('20100101T0000Z/b', ('20100101T0000Z/a',)),
        ('20100101T0600Z/a', ('20100101T0000Z/a', '20100101T0000Z/b')),
        ('20100101T0600Z/b', ('20100101T0600Z/a',)),
        ('20100101T1200Z/a', ('20100101T0600Z/a', '20100101T0600Z/b')),
        ('20100101T1200Z/b', ('20100101T1200Z/a',)),
        ('20100101T1800Z/a', ('20100101T1200Z/a', '20100101T1200Z/b')),
        ('20100101T1800Z/b', ('20100101T1800Z/a',)),
        ('20100102T0000Z/a', ('20100101T1800Z/a', '20100101T1800Z/b')),
        ('20100102T0000Z/b', ('20100102T0000Z/a',)),
    }


async def test_over_bracketed(flow, scheduler, reftest):
    """Test nested conditional simplification for pre-initial cycling."""
    wid = flow({
        'scheduling': {
            'initial cycle point': '2013-12-25T12:00Z',
            'final cycle point': '2013-12-25T12:00Z',
            'graph': {
                'T12': '''
                    (a[-P1D]:fail | b[-P1D]:fail | c[-P1D]:fail) => d
                    a & b & c  # Implied by implicit cycling now...
                ''',
            },
        },
    })
    schd = scheduler(wid, paused_start=False)

    assert await reftest(schd) == {
        ('20131225T1200Z/c', None),
        ('20131225T1200Z/d', ('20131224T1200Z/a', '20131224T1200Z/b', '20131224T1200Z/c')),
        ('20131225T1200Z/a', None),
        ('20131225T1200Z/b', None),
    }
