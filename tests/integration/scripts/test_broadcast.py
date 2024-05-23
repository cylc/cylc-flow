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

from cylc.flow.option_parsers import Options
from cylc.flow.scripts.broadcast import _main, get_option_parser


BroadcastOptions = Options(get_option_parser())


async def test_broadcast_multi(
    one_conf,
    flow,
    scheduler,
    start,
    run_dir,
    test_dir,
    capsys,
):
    """Test a multi-workflow broadcast command."""
    # create three workflows
    one = scheduler(flow(one_conf))
    two = scheduler(flow(one_conf))
    thr = scheduler(flow(one_conf))

    # the ID under which all three are installed
    id_base = test_dir.relative_to(run_dir)

    async with start(one):
        async with start(two):
            async with start(thr):
                capsys.readouterr()

                # test a successful broadcast command
                rets = await _main(
                    BroadcastOptions(settings=['script=true']), f'{id_base}*'
                )

                # all three broadcasts should have succeeded
                assert list(rets.values()) == [True, True, True]

                out, err = capsys.readouterr()
                assert '[*/root] script=true' in out
                assert err == ''

                # test an unsuccessful broadcast command
                rets = await _main(
                    BroadcastOptions(
                        namespaces=['*'],
                        settings=['script=true'],
                    ),
                    f'{id_base}*',
                )

                # all three broadcasts should have failed
                assert list(rets.values()) == [False, False, False]

                out, err = capsys.readouterr()
                assert '[*/root] script=true' not in out
                assert (
                    # NOTE: for historical reasons this message goes to stdout
                    # not stderr
                    'Rejected broadcast:'
                    ' settings are not compatible with the workflow'
                ) in out
                assert err == ''
