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

"""Test logic pertaining to the stop after cycle points.

This may be defined in different ways:
* In the workflow configuration.
* On the command line.
* Or loaded from the database.

When the workflow hits the "stop after" point, it should be wiped (i.e. set
to None).
"""

from typing import Optional

from cylc.flow import commands
from cylc.flow.cycling.integer import IntegerPoint
from cylc.flow.id import Tokens
from cylc.flow.workflow_status import StopMode


async def test_stop_after_cycle_point(
    flow,
    scheduler,
    run,
    reflog,
    complete,
):
    """Test the stop after cycle point.

    This ensures:
    * The stop after point gets loaded from the config.
    * The workflow stops when it hits this point.
    * The point gets wiped when the workflow hits this point.
    * The point is stored/retrieved from the DB as appropriate.

    """
    async def stops_after_cycle(schd) -> Optional[str]:
        """Run the workflow until it stops and return the cycle point."""
        triggers = reflog(schd)
        await complete(schd, timeout=2)
        assert len(triggers) == 1  # only one task (i.e. cycle) should be run
        return Tokens(list(triggers)[0][0], relative=True)['cycle']

    def get_db_value(schd) -> Optional[str]:
        """Return the cycle point value stored in the DB."""
        with schd.workflow_db_mgr.get_pri_dao() as pri_dao:
            return dict(pri_dao.select_workflow_params())['stopcp']

    config = {
        'scheduling': {
            'cycling mode': 'integer',
            'initial cycle point': '1',
            'stop after cycle point': '1',
            'graph': {
                'P1': 'a[-P1] => a',
            },
        },
    }
    id_ = flow(config)
    schd = scheduler(id_, paused_start=False)
    async with run(schd):
        # the cycle point should be loaded from the workflow configuration
        assert schd.config.stop_point == IntegerPoint('1')

        # this value should *not* be written to the database
        assert get_db_value(schd) is None

        # the workflow should stop after cycle 1
        assert await stops_after_cycle(schd) == '1'

    # change the configured cycle point to "2"
    config['scheduling']['stop after cycle point'] = '2'
    id_ = flow(config, id_=id_)
    schd = scheduler(id_, paused_start=False)
    async with run(schd):
        # the cycle point should be reloaded from the workflow configuration
        assert schd.config.stop_point == IntegerPoint('2')

        # this value should not be written to the database
        assert get_db_value(schd) is None

        # the workflow should stop after cycle 2
        assert await stops_after_cycle(schd) == '2'

    # override the configured value via the CLI option
    schd = scheduler(id_, paused_start=False, **{'stopcp': '3'})
    async with run(schd):
        # the CLI should take precedence over the config
        assert schd.config.stop_point == IntegerPoint('3')

        # this value *should* be written to the database
        assert get_db_value(schd) == '3'

        # the workflow should stop after cycle 3
        assert await stops_after_cycle(schd) == '3'

    # once the workflow hits this point, it should get cleared
    assert get_db_value(schd) is None

    schd = scheduler(id_, paused_start=False)
    async with run(schd):
        # the workflow should fall back to the configured value
        assert schd.config.stop_point == IntegerPoint('2')

        # override this value whilst the workflow is running
        await commands.run_cmd(
            commands.stop(
                schd,
                cycle_point=IntegerPoint('4'),
                mode=StopMode.REQUEST_CLEAN,
            )
        )
        assert schd.config.stop_point == IntegerPoint('4')

    # the new *should* be written to the database
    assert get_db_value(schd) == '4'

    schd = scheduler(id_, paused_start=False)
    async with run(schd):
        # the workflow should stop after cycle 4
        assert await stops_after_cycle(schd) == '4'
