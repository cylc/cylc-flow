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

from cylc.flow.exceptions import ClientError
from cylc.flow.tui.data import _show


async def test_show(flow, scheduler, start, rakiura, monkeypatch):
    """Test "cylc show" support in Tui."""
    id_ = flow({
        'scheduling': {
            'graph': {
                'R1': 'foo'
            },
        },
        'runtime': {
            'foo': {
                'meta': {
                    'title': 'Foo',
                    'description': 'The first metasyntactic variable.'
                },
            },
        },
    }, name='one')
    schd = scheduler(id_)
    async with start(schd):
        await schd.update_data_structure()

        with rakiura(size='80,40') as rk:
            rk.user_input('down', 'right')
            rk.wait_until_loaded(schd.tokens.id)

            # select a task
            rk.user_input('down', 'down', 'enter')

            # select the "show" context option
            rk.user_input(*(['down'] * 7), 'enter')
            rk.compare_screenshot(
                'success',
                'the show output should be displayed',
            )

            # make it look like "cylc show" failed
            def cli_cmd_fail(*args, **kwargs):
                raise ClientError(':(')
            monkeypatch.setattr(
                'cylc.flow.tui.data.cli_cmd',
                cli_cmd_fail,
            )

            # select the "show" context option
            rk.user_input('q', 'enter', *(['down'] * 7), 'enter')
            rk.compare_screenshot(
                'fail',
                'the error should be displayed',
            )
