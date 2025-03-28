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
#
# Tests for functions contained in cylc.flow.scripts.profiler
from cylc.flow.scripts.profiler import (parse_memory_file,
                                        parse_cpu_file,
                                        write_data,
                                        get_cgroup_dir,
                                        get_cgroup_version)
from unittest.mock import patch
import pytest


def test_parse_memory_file(mocker):

    with pytest.raises(FileNotFoundError):
        parse_memory_file("non_existent_file.txt")

    # Mock the 'open' function call to return a file object.
    mock_file = mocker.mock_open(read_data="1024")
    mocker.patch("builtins.open", mock_file)

    # Test the parse_memory_file function
    assert parse_memory_file("mocked_file.txt") == 1

    # Assert that the 'open' function was called with the expected arguments.
    mock_file.assert_called_once_with("mocked_file.txt", "r")


def test_parse_cpu_file(mocker):
    with pytest.raises(FileNotFoundError):
        parse_cpu_file("non_existent_file.txt", 1)

    # Mock the 'open' function call to return a file object.
    mock_file = mocker.mock_open(read_data="usage_usec 1000000")
    mocker.patch("builtins.open", mock_file)

    assert parse_cpu_file("mocked_file.txt", 1) == 1000
    mock_file.assert_called_once_with("mocked_file.txt", "r")

    mock_file = mocker.mock_open(read_data="1000000")
    mocker.patch("builtins.open", mock_file)
    assert parse_cpu_file("mocked_file.txt", 2) == 1
    mock_file.assert_called_once_with("mocked_file.txt", "r")


def test_write_data(tmpdir):
    # Create tmp file
    file = tmpdir.join('output.txt')

    write_data('test_data', file.strpath)
    assert file.read() == 'test_data\n'


def test_get_cgroup_dir(mocker):

    mock_file = mocker.mock_open(read_data="0::bad/test/cgroup/place")
    mocker.patch("builtins.open", mock_file)
    with pytest.raises(AttributeError):
        get_cgroup_dir()

    mock_file = mocker.mock_open(read_data="0::good/cgroup/place/2222222")
    mocker.patch("builtins.open", mock_file)
    assert get_cgroup_dir() == "good/cgroup/place/2222222"


def test_get_cgroup_version(mocker):

    # Mock the Path.exists function call to return True
    mocker.patch("pathlib.Path.exists", return_value=True)
    assert get_cgroup_version('stuff/in/place', 'more_stuff') == 1

    with patch('pathlib.Path.exists', side_effect=[False, True]):
        assert get_cgroup_version('stuff/in/place', 'more_stuff') == 2

    # Mock the Path.exists function call to return False
    mocker.patch("pathlib.Path.exists", return_value=False)
    assert get_cgroup_version('stuff/in/other/place', 'things') is None