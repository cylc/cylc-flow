# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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

from cylc.flow.data_store_mgr import task_mean_elapsed_time, parse_job_item


def int_id():
    return '20130808T00/foo/03'


class FakeTDef:
    elapsed_times = (0.0, 10.0)


def test_task_mean_elapsed_time():
    tdef = FakeTDef()
    result = task_mean_elapsed_time(tdef)
    assert result == 5.0


def test_parse_job_item():
    """Test internal id parsing method."""
    point, name, sub_num = parse_job_item(int_id())
    tpoint, tname, tsub_num = int_id().split('/', 2)
    assert (point, name, sub_num) == (tpoint, tname, int(tsub_num))
    tpoint, tname, tsub_num = parse_job_item(f'{point}/{name}')
    assert name, None == (point, (tpoint, tname, tsub_num))
    tpoint, tname, tsub_num = parse_job_item(f'{name}.{point}.{sub_num}')
    assert name, sub_num == (point, (tpoint, tname, tsub_num))
    tpoint, tname, tsub_num = parse_job_item(f'{name}.{point}.NotNumber')
    assert name, None == (point, (tpoint, tname, tsub_num))
    tpoint, tname, tsub_num = parse_job_item(f'{name}.{point}')
    assert name, None == (point, (tpoint, tname, tsub_num))
    tpoint, tname, tsub_num = parse_job_item(f'{name}')
    assert name, None == (None, (tpoint, tname, tsub_num))
