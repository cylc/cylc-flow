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
                                        get_cgroup_name,
                                        get_cgroup_version,
                                        get_cgroup_paths,
                                        get_config,
                                        stop_profiler,
                                        profile)
import pytest
import argparse
from unittest import mock


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

    assert parse_cpu_file(
        "mocked_file.txt", 1) == 1000
    mock_file.assert_called_once_with("mocked_file.txt", "r")

    mock_file = mocker.mock_open(read_data="1000000")
    mocker.patch("builtins.open", mock_file)
    assert parse_cpu_file("mocked_file.txt", 2) == 1
    mock_file.assert_called_once_with("mocked_file.txt", "r")


def test_write_data(tmpdir):
    # Create tmp file
    file = tmpdir.join('output.txt')

    write_data('test_memory', 'test_cpu', file.strpath)
    assert file.read() == ('{\n    "max_rss": "test_memory",\n'
                           '    "cpu_time": "test_cpu"\n}')


def test_get_cgroup_name(mocker):

    mock_file = mocker.mock_open(read_data="0::bad/test/cgroup/place")
    mocker.patch("builtins.open", mock_file)
    with pytest.raises(AttributeError):
        get_cgroup_name()

    mock_file = mocker.mock_open(read_data="0::good/cgroup/place/2222222")
    mocker.patch("builtins.open", mock_file)
    assert get_cgroup_name() == "good/cgroup/place/2222222"


def test_get_cgroup_name_file_not_found(mocker):

    def mock_os_pid():
        return 'The Thing That Should Not Be'

    mocker.patch("os.getpid", mock_os_pid)
    with pytest.raises(FileNotFoundError):
        get_cgroup_name()


def test_get_cgroup_version(mocker):

    # Mock the Path.exists function call to return True
    mocker.patch("pathlib.Path.exists", return_value=True)
    assert get_cgroup_version('stuff/in/place',
                              'more_stuff') == 1

    with mock.patch('pathlib.Path.exists', side_effect=[False, True]):
        assert get_cgroup_version('stuff/in/place',
                                  'more_stuff') == 2

    # Mock the Path.exists function call to return False
    mocker.patch("pathlib.Path.exists", return_value=False)
    with pytest.raises(FileNotFoundError):
        get_cgroup_version('stuff/in/other/place',
                           'things')


def test_get_cgroup_paths():

    process = get_cgroup_paths(1, "test_location/",
                               "test_name")
    assert process.cgroup_memory_path == "test_location/test_name/memory.peak"
    assert process.cgroup_cpu_path == "test_location/test_name/cpu.stat"

    process = get_cgroup_paths(2, "test_location",
                               "/test_name")
    assert (process.cgroup_memory_path ==
            "test_location/memory/test_name/memory.max_usage_in_bytes")
    assert (process.cgroup_cpu_path ==
            "test_location/cpu/test_name/cpuacct.usage")


def test_profile_data(mocker):
    process = get_cgroup_paths(1, "test_location/",
                               "test_name")

    mock_file = mocker.mock_open(read_data="")
    mocker.patch("builtins.open", mock_file)
    mocker.patch("cylc.flow.scripts.profiler.parse_memory_file",
                 return_value=0)
    mocker.patch("cylc.flow.scripts.profiler.parse_cpu_file",
                 return_value=2048)
    run_once = mock.Mock(side_effect=[True, False])
    profile(process, 1, 1, run_once)
    mock_file.assert_called_with("profiler.json", "w")


def test_stop_profiler():
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        stop_profiler()
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 0


def test_profile_1(mocker):
    process = get_cgroup_paths(
        1, "test_location/", "test_name")

    mock_file = mocker.mock_open(read_data="")
    mocker.patch("builtins.open", mock_file)
    mocker.patch(
        "cylc.flow.scripts.profiler.parse_memory_file", return_value=1024)
    mocker.patch(
        "cylc.flow.scripts.profiler.parse_cpu_file", return_value=2048)
    run_once = mock.Mock(side_effect=[True, False])

    profile(process, 1, 1, run_once)
    mock_file.assert_called_with("profiler.json", "w")


def test_profile_2(mocker):
    # assert_called_with only shows the last call to open().
    # Setting peak memory to zero stops the memory call to open
    process = get_cgroup_paths(
        1, "test_location/", "test_name")

    mock_file = mocker.mock_open(read_data="")
    mocker.patch("builtins.open", mock_file)
    mocker.patch(
        "cylc.flow.scripts.profiler.parse_cpu_file", return_value=2048)
    mocker.patch(
        "cylc.flow.scripts.profiler.parse_memory_file", return_value=0)
    run_once = mock.Mock(side_effect=[True, False])

    profile(process, 1, 1, run_once)
    mock_file.assert_called_with("profiler.json", "w")


def test_get_config(mocker):

    # Mock the 'open' function call to return a valid string.
    mock_file = mocker.mock_open(read_data="0::good/cgroup/place/2222222")
    mocker.patch("builtins.open", mock_file)

    # Mock the get_cgroup_version function so it says the cgroup path is valid
    mocker.patch("cylc.flow.scripts.profiler.get_cgroup_version",
                 return_value=1)
    # Mock the parse functions so they return valid values
    mocker.patch("cylc.flow.scripts.profiler.parse_memory_file",
                 return_value=1024)
    mocker.patch("cylc.flow.scripts.profiler.parse_cpu_file",
                 return_value=2048)

    # Mock the write_data function to simulate writing data.
    # It will error out on the 3rd call
    mock_write = mock.Mock(
        side_effect=[None, None, FileNotFoundError('Carpe Diem')])
    mocker.patch("cylc.flow.scripts.profiler.write_data", mock_write)

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-i", type=int, default=10, dest="delay")
    parser.add_argument(
        "-m", type=str, default="test_location/",
        dest="cgroup_location")
    with pytest.raises(FileNotFoundError):
        get_config(parser.parse_args())
