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
                                        parse_memory_allocated,
                                        get_cgroup_name,
                                        get_cgroup_version,
                                        get_cgroup_paths,
                                        get_resource_usage,
                                        stop_profiler,
                                        profile,
                                        Process)
import pytest
from unittest import mock


def test_stop_profiler(mocker, monkeypatch, tmpdir):
    monkeypatch.setenv('CYLC_WORKFLOW_ID', "test_value")

    def mock_get_client(env_var, timeout=None):
        return True

    class MockedClient():
        def __init__(self, *a, **k):
            pass

        async def async_request(self, *a, **k):
            pass

    mocker.patch("cylc.flow.scripts.profiler.get_client", MockedClient)

    mem_file = tmpdir.join("memory_file.txt")
    mem_file.write('1234')
    cpu_file = tmpdir.join("cpu_file.txt")
    cpu_file.write('5678')
    mem_allocated_file = tmpdir.join("memory_allocated.txt")
    mem_allocated_file.write('99999')

    process_object = Process(
        cgroup_memory_path=mem_file,
        cgroup_cpu_path=cpu_file,
        memory_allocated_path=mem_allocated_file,
        cgroup_version=1)
    with pytest.raises(SystemExit) as excinfo:
        stop_profiler(process_object, 1)

    assert excinfo.type == SystemExit
    assert excinfo.value.code == 0


def test_get_resource_usage(mocker, monkeypatch, tmpdir):
    monkeypatch.setenv('CYLC_WORKFLOW_ID', "test_value")

    process_object = Process(
        cgroup_memory_path=None,
        cgroup_cpu_path=None,
        memory_allocated_path=None,
        cgroup_version=1)

    max_rss, cpu_time, memory_allocated = get_resource_usage(process_object)

    assert max_rss == 0
    assert cpu_time == 0
    assert memory_allocated == 0


def test_parse_memory_file(mocker, tmpdir):

    mem_file_v1 = tmpdir.join("memory_file_v1.txt")
    mem_file_v1.write('total_rss=1024')
    mem_file_v2 = tmpdir.join("memory_file_v2.txt")
    mem_file_v2.write('anon=666')
    cpu_file = tmpdir.join("cpu_file.txt")
    cpu_file.write('5678')
    mem_allocated_file = tmpdir.join("memory_allocated.txt")
    mem_allocated_file.write('99999')

    good_process_object_v1 = Process(
        cgroup_memory_path=mem_file_v1,
        cgroup_cpu_path=cpu_file,
        memory_allocated_path=mem_allocated_file,
        cgroup_version=1)
    good_process_object_v2 = Process(
        cgroup_memory_path=mem_file_v2,
        cgroup_cpu_path=cpu_file,
        memory_allocated_path=mem_allocated_file,
        cgroup_version=2)
    bad_process_object = Process(
        cgroup_memory_path='',
        cgroup_cpu_path='',
        memory_allocated_path='',
        cgroup_version=1)

    with pytest.raises(FileNotFoundError):
        parse_memory_file(bad_process_object)

    # Test the parse_memory_file function
    assert parse_memory_file(good_process_object_v1) == 1024
    assert parse_memory_file(good_process_object_v2) == 666


def test_parse_cpu_file(mocker, tmpdir):

    mem_file = tmpdir.join("memory_file.txt")
    mem_file.write('1024')
    cpu_file_v1 = tmpdir.join("cpu_file_v1.txt")
    cpu_file_v1.write('1234567890')
    cpu_file_v2 = tmpdir.join("cpu_file_v2.txt")
    cpu_file_v2.write('usage_usec=1234567890')
    cpu_file_v2_bad = tmpdir.join("cpu_file_v2_bad.txt")
    cpu_file_v2_bad.write('Give me fuel, give me fire, '
                          'give me that which I desire')
    mem_allocated_file = tmpdir.join("memory_allocated.txt")
    mem_allocated_file.write('99999')

    good_process_object_v1 = Process(
        cgroup_memory_path=mem_file,
        cgroup_cpu_path=cpu_file_v1,
        memory_allocated_path=mem_allocated_file,
        cgroup_version=1)
    good_process_object_v2 = Process(
        cgroup_memory_path=mem_file,
        cgroup_cpu_path=cpu_file_v2,
        memory_allocated_path=mem_allocated_file,
        cgroup_version=2)
    bad_process_object = Process(
        cgroup_memory_path='',
        cgroup_cpu_path='',
        memory_allocated_path='',
        cgroup_version=1)
    bad_process_object_v2 = Process(
        cgroup_memory_path=mem_file,
        cgroup_cpu_path=cpu_file_v2_bad,
        memory_allocated_path=mem_allocated_file,
        cgroup_version=2)

    assert parse_cpu_file(good_process_object_v1) == 1234
    assert parse_cpu_file(good_process_object_v2) == 1234567

    with pytest.raises(FileNotFoundError):
        parse_cpu_file(bad_process_object)
    with pytest.raises(ValueError):
        parse_cpu_file(bad_process_object_v2)


def test_get_cgroup_name(mocker):

    mock_file = mocker.mock_open(read_data="0::bad/test/cgroup/place")
    mocker.patch("builtins.open", mock_file)
    with pytest.raises(AttributeError):
        get_cgroup_name()

    mock_file = mocker.mock_open(read_data="0::good/cgroup/place/2222222")
    mocker.patch("builtins.open", mock_file)
    assert get_cgroup_name() == "good/cgroup/place/2222222"


def test_parse_memory_allocated(mocker, tmpdir):
    mem_allocated_file = tmpdir.join("memory.max")
    mem_allocated_file.write('99999')

    # We currently do not track memory allocated for cgroups v1
    good_process_object_v1 = Process(
        cgroup_memory_path='',
        cgroup_cpu_path='',
        memory_allocated_path=tmpdir,
        cgroup_version=1)

    good_process_object_v2 = Process(
        cgroup_memory_path='',
        cgroup_cpu_path='',
        memory_allocated_path=tmpdir,
        cgroup_version=2)

    bad_process_object_v2 = Process(
        cgroup_memory_path='',
        cgroup_cpu_path='',
        memory_allocated_path='/',
        cgroup_version=2)

    assert parse_memory_allocated(good_process_object_v1) == 0
    assert parse_memory_allocated(good_process_object_v2) == 99999
    with pytest.raises(FileNotFoundError):
        parse_memory_file(bad_process_object_v2)


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
                              'more_stuff') == 2

    with mock.patch('pathlib.Path.exists', side_effect=[False, True]):
        assert get_cgroup_version('stuff/in/place',
                                  'more_stuff') == 1

    # Mock the Path.exists function call to return False
    mocker.patch("pathlib.Path.exists", return_value=False)
    with pytest.raises(FileNotFoundError):
        get_cgroup_version('stuff/in/other/place',
                           'things')


def test_get_cgroup_paths(mocker):
    mocker.patch("cylc.flow.scripts.profiler.get_cgroup_name",
                 return_value='test_name')
    mocker.patch("cylc.flow.scripts.profiler.get_cgroup_version",
                 return_value=2)
    process = get_cgroup_paths("test_location/")
    assert process.cgroup_memory_path == "test_location/test_name/memory.stat"
    assert process.cgroup_cpu_path == "test_location/test_name/cpu.stat"

    mocker.patch("cylc.flow.scripts.profiler.get_cgroup_name",
                 return_value='test_name')
    mocker.patch("cylc.flow.scripts.profiler.get_cgroup_version",
                 return_value=1)

    process = get_cgroup_paths("test_location/")
    assert (process.cgroup_memory_path ==
            "test_location/memory/test_name/memory.stat")
    assert (process.cgroup_cpu_path ==
            "test_location/cpu/test_name/cpuacct.usage")

    mocker.patch("cylc.flow.scripts.profiler.get_cgroup_name",
                 return_value='test_name')
    mocker.patch("cylc.flow.scripts.profiler.get_cgroup_version",
                 return_value=3)
    with pytest.raises(ValueError):
        get_cgroup_paths("test_location/")


def test_profile_data(mocker):
    # This test should run without error
    mocker.patch("cylc.flow.scripts.profiler.get_cgroup_name",
                 return_value='test_name')
    mocker.patch("cylc.flow.scripts.profiler.get_cgroup_version",
                 return_value=2)
    process = get_cgroup_paths("test_location/")

    mock_file = mocker.mock_open(read_data="")
    mocker.patch("builtins.open", mock_file)
    mocker.patch("cylc.flow.scripts.profiler.parse_memory_file",
                 return_value=0)
    mocker.patch("cylc.flow.scripts.profiler.parse_cpu_file",
                 return_value=2048)
    run_once = mock.Mock(side_effect=[True, False])
    profile(process, 1, run_once)


@pytest.fixture
def options(mocker):
    opts = mocker.Mock()
    opts.cgroup_location = "/fake/path"
    opts.comms_timeout = 10
    opts.delay = 1
    return opts


def test_main(mocker, options):
    mock_get_cgroup_paths = mocker.patch(
        "cylc.flow.scripts.profiler.get_cgroup_paths"
    )
    mock_signal = mocker.patch("cylc.flow.scripts.profiler.signal.signal")
    mock_profile = mocker.patch("cylc.flow.scripts.profiler.profile")

    mock_get_cgroup_paths.return_value = mocker.Mock()

    from cylc.flow.scripts.profiler import _main
    _main(options)

    mock_get_cgroup_paths.assert_called_once_with("/fake/path")
    assert mock_signal.call_count == 3
    mock_profile.assert_called_once()
