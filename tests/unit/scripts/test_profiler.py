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
import asyncio
import logging
from pathlib import Path
from unittest import mock

import pytest

from cylc.flow import CYLC_LOG
from cylc.flow.exceptions import CylcProfilerError
from cylc.flow.scripts.profiler import (
    Process,
    _main,
    get_cgroup_name,
    get_cgroup_names,
    get_cgroup_paths,
    get_cgroup_version,
    get_option_parser,
    get_profiler_data,
    main,
    parse_cpu_file,
    parse_memory_allocated,
    parse_memory_file,
    profile,
    report_to_scheduler,
    v2_controllers_enabled,
)


async def test_report_to_scheduler(monkeypatch, tmpdir):
    """It should capture and record profiler data."""
    monkeypatch.setenv('CYLC_WORKFLOW_ID', "test_value")
    monkeypatch.setenv('CYLC_TASK_JOB', "test_task_job")

    # capture record_messages calls
    record_messages = mock.AsyncMock()
    monkeypatch.setattr(
        'cylc.flow.scripts.profiler.record_messages', record_messages
    )

    # mock the cGroup filesystem
    mem_file = tmpdir.join("memory_file.txt")
    mem_file.write('total_rss=1234')
    cpu_file = tmpdir.join("cpu_file.txt")
    cpu_file.write('5678000')
    # NOTE: memory allocated is not available for cGroups v1
    mem_allocated_file = tmpdir.join("memory_allocated.txt")
    mem_allocated_file.write('99999')

    process_object = Process(
        cgroup_memory_path=mem_file,
        cgroup_cpu_path=cpu_file,
        memory_allocated_path=mem_allocated_file,
        memory_version=1,
        cpu_version=1,
        max_rss=42,
    )

    await report_to_scheduler(process_object, 1)

    # the profiler should record a "cylc message" with the profiler data
    assert record_messages.call_args_list == [
        mock.call(
            'test_value',
            'test_task_job',
            [
                [
                    'DEBUG',
                    '_cylc_profiler:'
                    ' {"max_rss": 42, "cpu_time": 6, "memory_allocated": 0}',
                ]
            ],
            comms_timeout=1,
        )
    ]


def test_get_resource_usage():
    """It should return None if cGroup information is not provided."""
    process_object = Process(
        cgroup_memory_path=None,
        cgroup_cpu_path=None,
        memory_allocated_path=None,
        memory_version=1,
        cpu_version=1,
        max_rss=0)

    assert get_profiler_data(process_object) == {
        'max_rss': None,
        'cpu_time': None,
        'memory_allocated': None,
    }


def test_parse_memory_file(tmpdir):
    """It should return the memory usage of the process."""
    mem_file_v1 = tmpdir.join("memory_file_v1.txt")
    # 2 MiB in bytes
    mem_file_v1.write('total_rss=2097152')
    mem_file_v2 = tmpdir.join("memory_file_v2.txt")
    # 3 MiB in bytes
    mem_file_v2.write('anon=3145728')
    cpu_file = tmpdir.join("cpu_file.txt")
    cpu_file.write('5678')
    mem_allocated_file = tmpdir.join("memory_allocated.txt")
    mem_allocated_file.write('99999')

    good_process_object_v1 = Process(
        cgroup_memory_path=mem_file_v1,
        cgroup_cpu_path=cpu_file,
        memory_allocated_path=mem_allocated_file,
        memory_version=1,
        cpu_version=1,
        max_rss=0)
    good_process_object_v2 = Process(
        cgroup_memory_path=mem_file_v2,
        cgroup_cpu_path=cpu_file,
        memory_allocated_path=mem_allocated_file,
        memory_version=2,
        cpu_version=2,
        max_rss=0)
    bad_process_object = Process(
        cgroup_memory_path='',
        cgroup_cpu_path='',
        memory_allocated_path='',
        memory_version=1,
        cpu_version=1,
        max_rss=0)

    with pytest.raises(CylcProfilerError) as excinfo:
        parse_memory_file(bad_process_object)
    assert "Unable to find memory usage data" in str(excinfo.value)

    # Test the parse_memory_file function (values reported in bytes)
    assert parse_memory_file(good_process_object_v1) == 2097152
    assert parse_memory_file(good_process_object_v2) == 3145728


def test_parse_cpu_file(tmpdir):
    """It should return the cpu usage of the process."""
    mem_file = tmpdir.join("memory_file.txt")
    mem_file.write('1024')
    cpu_file_v1_good = tmpdir.join("cpu_file_v1_good.txt")
    cpu_file_v1_good.write('1234567890')
    cpu_file_v1_bad = tmpdir.join("cpu_file_v1_bad.txt")
    cpu_file_v1_bad.write("I'm your dream, mind ashtray")
    cpu_file_v2_good = tmpdir.join("cpu_file_v2_good.txt")
    cpu_file_v2_good.write('usage_usec 1234567890')
    cpu_file_v2_bad = tmpdir.join("cpu_file_v2_bad.txt")
    cpu_file_v2_bad.write('Give me fuel, give me fire, '
                          'give me that which I desire')
    mem_allocated_file = tmpdir.join("memory_allocated.txt")
    mem_allocated_file.write('99999')

    good_process_object_v1 = Process(
        cgroup_memory_path=mem_file,
        cgroup_cpu_path=cpu_file_v1_good,
        memory_allocated_path=mem_allocated_file,
        memory_version=1,
        cpu_version=1,
        max_rss=0)
    good_process_object_v2 = Process(
        cgroup_memory_path=mem_file,
        cgroup_cpu_path=cpu_file_v2_good,
        memory_allocated_path=mem_allocated_file,
        memory_version=2,
        cpu_version=2,
        max_rss=0)
    bad_process_object_v1_1 = Process(
        cgroup_memory_path='',
        cgroup_cpu_path='',
        memory_allocated_path='',
        memory_version=1,
        cpu_version=1,
        max_rss=0)
    bad_process_object_v1_2 = Process(
        cgroup_memory_path=mem_file,
        cgroup_cpu_path=cpu_file_v1_bad,
        memory_allocated_path=mem_allocated_file,
        memory_version=1,
        cpu_version=1,
        max_rss=0)
    bad_process_object_v2 = Process(
        cgroup_memory_path=mem_file,
        cgroup_cpu_path=cpu_file_v2_bad,
        memory_allocated_path=mem_allocated_file,
        memory_version=2,
        cpu_version=2,
        max_rss=0)

    assert parse_cpu_file(good_process_object_v1) == 1235
    assert parse_cpu_file(good_process_object_v2) == 1234568

    with pytest.raises(CylcProfilerError) as excinfo:
        parse_cpu_file(bad_process_object_v1_1)
    assert "Unable to find cpu usage data" in str(excinfo.value)
    with pytest.raises(CylcProfilerError) as excinfo:
        parse_cpu_file(bad_process_object_v1_2)
    assert "Unable to find cpu usage data" in str(excinfo.value)
    with pytest.raises(CylcProfilerError) as excinfo:
        parse_cpu_file(bad_process_object_v2)
    assert "Unable to find cpu usage data" in str(excinfo.value)


def test_get_cgroup_name(mocker):
    """It should return the cgroup name of the process."""
    mocker.patch.object(
        Path, 'read_text', return_value="0::bad/test/cgroup/place"
    )
    with pytest.raises(CylcProfilerError):
        get_cgroup_name()

    mocker.patch.object(
        Path, 'read_text', return_value="0::good/cgroup/place/2222222"
    )
    assert get_cgroup_name() == "good/cgroup/place/2222222"


def test_parse_memory_allocated(tmp_path_factory):
    """It should return the memory allocated to the process."""
    good_mem_dir = tmp_path_factory.mktemp("mem_dir")
    mem_allocated_file = good_mem_dir / "memory.max"
    # 100 MiB in bytes
    mem_allocated_file.write_text('104857600')
    # the cgroups v1 equivalent
    (good_mem_dir / "memory.limit_in_bytes").write_text('104857600')

    good_process_object_v1 = Process(
        cgroup_memory_path=good_mem_dir / "memory.stat",
        cgroup_cpu_path='',
        memory_allocated_path=good_mem_dir,
        memory_version=1,
        cpu_version=1,
        max_rss=0)

    good_process_object_v2 = Process(
        cgroup_memory_path='',
        cgroup_cpu_path='',
        memory_allocated_path=good_mem_dir,
        memory_version=2,
        cpu_version=2,
        max_rss=0)

    bad_process_object_v2_1 = Process(
        cgroup_memory_path='',
        cgroup_cpu_path='',
        memory_allocated_path=Path('/'),
        memory_version=2,
        cpu_version=2,
        max_rss=0)

    assert parse_memory_allocated(good_process_object_v1) == 104857600
    assert parse_memory_allocated(good_process_object_v2) == 104857600
    with pytest.raises(CylcProfilerError) as excinfo:
        parse_memory_file(bad_process_object_v2_1)
    assert "Unable to find memory usage data" in str(excinfo.value)
    # Nested directories with 'max' value
    base_dir = tmp_path_factory.mktemp("base")

    dir_1 = base_dir / "dir_1"
    dir_1.mkdir()
    mem_file_1 = dir_1 / "memory.max"
    mem_file_1.write_text("max")

    dir_2 = dir_1 / "dir_2"
    dir_2.mkdir()
    mem_file_2 = dir_2 / "memory.max"
    mem_file_2.write_text("max")

    dir_3 = dir_2 / "dir_3"
    dir_3.mkdir()
    mem_file_3 = dir_3 / "memory.max"
    mem_file_3.write_text("max")

    dir_4 = dir_3 / "dir_4"
    dir_4.mkdir()
    mem_file_4 = dir_4 / "memory.max"
    mem_file_4.write_text("max")

    dir_5 = dir_4 / "dir_5"
    dir_5.mkdir()
    mem_file_5 = dir_5 / "memory.max"
    mem_file_5.write_text("max")

    bad_process_object_v2_2 = Process(
        cgroup_memory_path='',
        cgroup_cpu_path='',
        memory_allocated_path=dir_5,
        memory_version=2,
        cpu_version=2,
        max_rss=0)

    # The function should return 0 if it cannot find a memory.max file with
    # a value
    assert parse_memory_allocated(bad_process_object_v2_2) == 0

    # Add a memory.max file with a value to the top level directory
    # and check it is read
    mem_file_1.write_text("104857600")
    assert parse_memory_allocated(bad_process_object_v2_2) == 104857600

    # cgroups v1 (e.g. PBS in hybrid mode) uses memory.limit_in_bytes, and a
    # huge number rather than "max" to mean "unlimited". The cgroup dir is
    # taken from cgroup_memory_path as memory_allocated_path is not set.
    v1_dir = tmp_path_factory.mktemp("v1")
    job_dir = v1_dir / "jobid" / "2397344.ehz100"
    job_dir.mkdir(parents=True)
    (v1_dir / "memory.limit_in_bytes").write_text("9223372036854771712")
    (v1_dir / "jobid" / "memory.limit_in_bytes").write_text(
        "9223372036854771712"
    )
    (job_dir / "memory.limit_in_bytes").write_text("104857600")

    v1_process = Process(
        cgroup_memory_path=job_dir / "memory.stat",
        cgroup_cpu_path='',
        memory_allocated_path=job_dir,
        memory_version=1,
        cpu_version=1,
        max_rss=0)
    assert parse_memory_allocated(v1_process) == 104857600

    # the limit should be inherited from a parent cgroup if this one is
    # unlimited
    (job_dir / "memory.limit_in_bytes").write_text("9223372036854771712")
    (v1_dir / "jobid" / "memory.limit_in_bytes").write_text("104857600")
    assert parse_memory_allocated(v1_process) == 104857600

    # an unlimited v1 cgroup should report 0 rather than the sentinel value
    (v1_dir / "jobid" / "memory.limit_in_bytes").write_text(
        "9223372036854771712"
    )
    assert parse_memory_allocated(v1_process) == 0


def test_get_cgroup_name_file_not_found(mocker):
    """It should raise an error if the cgroup file is not found."""
    def mock_os_pid():
        return 'The Thing That Should Not Be'

    mocker.patch("os.getpid", mock_os_pid)
    with pytest.raises(CylcProfilerError) as excinfo:
        get_cgroup_name()
    assert "/cgroup not found" in str(excinfo.value)


def test_get_cgroup_version(mocker):
    """It should return the cgroup version of the process."""
    # Mock the Path.exists function call to return True
    mocker.patch("pathlib.Path.exists", return_value=True)
    assert get_cgroup_version(Path('stuff/in/place'),
                              'more_stuff') == 2

    with mock.patch('pathlib.Path.exists', side_effect=[False, True]):
        assert get_cgroup_version(Path('stuff/in/place'),
                                  'more_stuff') == 1

    # Mock the Path.exists function call to return False
    mocker.patch("pathlib.Path.exists", return_value=False)
    with pytest.raises(CylcProfilerError) as excinfo:
        get_cgroup_version(Path('stuff/in/other/place'),
                           'things')
    assert "Cgroup not found" in str(excinfo.value)


def test_get_cgroup_paths(mocker, tmp_path):
    """It should locate the memory and cpu controllers independently."""
    # cgroups v2: both controllers in the unified hierarchy
    v2_names = {'v2': 'test_name', 'memory': 'test_name', 'cpu': 'test_name'}
    v2_loc = tmp_path / 'v2'
    (v2_loc / 'test_name').mkdir(parents=True)
    (v2_loc / 'test_name' / 'memory.stat').write_text('anon 1')
    (v2_loc / 'test_name' / 'cpu.stat').write_text('usage_usec 1')
    # a real v2 hierarchy has resource controllers enabled
    (v2_loc / 'test_name' / 'cgroup.controllers').write_text('memory pids')

    mocker.patch("cylc.flow.scripts.profiler.get_cgroup_names",
                 return_value=v2_names)
    process = get_cgroup_paths(v2_loc)
    assert process.memory_version == 2
    assert process.cpu_version == 2
    assert (process.cgroup_memory_path ==
            v2_loc / "test_name" / "memory.stat")
    assert process.cgroup_cpu_path == v2_loc / "test_name" / "cpu.stat"
    assert process.memory_allocated_path == v2_loc / "test_name"

    # cgroups v1: each controller mounted separately, no unified hierarchy
    v1_names = {'memory': 'test_name', 'cpu': 'test_name'}
    v1_loc = tmp_path / 'v1'
    (v1_loc / 'memory' / 'test_name').mkdir(parents=True)
    (v1_loc / 'memory' / 'test_name' / 'memory.stat').write_text('total_rss 1')
    (v1_loc / 'cpu' / 'test_name').mkdir(parents=True)
    (v1_loc / 'cpu' / 'test_name' / 'cpuacct.usage').write_text('1')

    mocker.patch("cylc.flow.scripts.profiler.get_cgroup_names",
                 return_value=v1_names)
    process = get_cgroup_paths(v1_loc)
    assert process.memory_version == 1
    assert process.cpu_version == 1
    assert (process.cgroup_memory_path ==
            v1_loc / "memory" / "test_name" / "memory.stat")
    assert (process.cgroup_cpu_path ==
            v1_loc / "cpu" / "test_name" / "cpuacct.usage")

    # systemd "hybrid" mode: a cgroup2 hierarchy is mounted for process
    # tracking only (cgroup.controllers is empty) and the resource
    # controllers stay on v1. The kernel still exposes cpu.stat in the v2
    # cgroup, but it describes the batch system's service cgroup - shared
    # by every job on the node - so it must NOT be preferred over v1.
    job = 'pbspro.service/jobid/2761065.ehz100'
    hybrid_names = {
        'v2': 'system.slice/pbs.service',
        'memory': job,
        'cpu': job,
        'cpuacct': job,
    }
    hy_loc = tmp_path / 'hybrid'
    (hy_loc / 'system.slice' / 'pbs.service').mkdir(parents=True)
    (hy_loc / 'system.slice' / 'pbs.service' / 'cpu.stat').write_text(
        'usage_usec 81514978331')
    (hy_loc / 'system.slice' / 'pbs.service' / 'cgroup.controllers'
     ).write_text('')
    (hy_loc / 'memory' / job).mkdir(parents=True)
    (hy_loc / 'memory' / job / 'memory.stat').write_text('total_rss 1')
    # the cpu and cpuacct controllers are co-mounted as "cpu,cpuacct"
    (hy_loc / 'cpu,cpuacct' / job).mkdir(parents=True)
    (hy_loc / 'cpu,cpuacct' / job / 'cpuacct.usage').write_text('1')

    mocker.patch("cylc.flow.scripts.profiler.get_cgroup_names",
                 return_value=hybrid_names)
    process = get_cgroup_paths(hy_loc)
    assert process.memory_version == 1
    assert process.cpu_version == 1
    assert (process.cgroup_cpu_path ==
            hy_loc / 'cpu,cpuacct' / job / 'cpuacct.usage')
    assert (process.cgroup_memory_path ==
            hy_loc / 'memory' / job / 'memory.stat')
    assert process.memory_allocated_path == hy_loc / 'memory' / job

    # neither version available
    with pytest.raises(CylcProfilerError) as excinfo:
        get_cgroup_paths(tmp_path / 'nothing_here')
    assert "Cgroup not found" in str(excinfo.value)


async def test_profile_data(mocker):
    """Test the profile function with mocked data to ensure it calls the parse
    functions and handles the data correctly."""
    process = Process(
        cgroup_memory_path=Path("test_location/test_name/memory.stat"),
        cgroup_cpu_path=Path("test_location/test_name/cpu.stat"),
        memory_allocated_path=Path("test_location/test_name"),
        memory_version=2,
        cpu_version=2,
        max_rss=0,
    )

    mock_file = mocker.mock_open(read_data="")
    mocker.patch("builtins.open", mock_file)
    mocker.patch("cylc.flow.scripts.profiler.parse_memory_file",
                 side_effect=[100, 200, 150])
    mocker.patch("cylc.flow.scripts.profiler.parse_cpu_file",
                 return_value=2048)

    # The profile function runs until the callable returns False.
    run_count = 0

    def run_four_times():
        nonlocal run_count
        run_count += 1
        return run_count < 4

    await profile(process, 0.1, run_four_times)

    # It should have been called 4 times before run_once returned False
    assert run_count == 4
    # The max_rss should be the highest value from parse_memory_file
    assert process.max_rss == 200


@pytest.fixture
def options(mocker):
    opts = mocker.Mock()
    opts.cgroup_location = "/fake/path"
    opts.cgroup_memory_path = "/another/fake/path"
    opts.comms_timeout = 10
    opts.delay = "PT1S"
    return opts


async def test_main(mocker, options, monkeypatch):
    """It should run the profiler and watch and kill functions concurrently."""
    # Mock Cylc env vars
    monkeypatch.setenv('CYLC_WORKFLOW_ID', "Exit Light")
    monkeypatch.setenv('CYLC_TASK_JOB', "Enter Night")

    # Mock the gets and parse functions to return something sensible
    # without needing actual files
    mocker.patch("cylc.flow.scripts.profiler.get_cgroup_paths",
                 return_value=Process(
                     cgroup_memory_path=Path("/some/place/memory.stat"),
                     cgroup_cpu_path=Path("/some/place/cpu.stat"),
                     memory_allocated_path=Path("/some/place"),
                     memory_version=2,
                     cpu_version=2,
                     max_rss=0,))
    mocker.patch("cylc.flow.scripts.profiler.parse_memory_file",
                 return_value=1234)
    mocker.patch("cylc.flow.scripts.profiler.parse_cpu_file",
                 return_value=5678)
    mocker.patch("cylc.flow.scripts.profiler.parse_memory_allocated",
                 return_value=90)

    mock_profile = mocker.patch("cylc.flow.scripts.profiler.profile")
    mock_watch_and_kill = mocker.patch(
        "cylc.flow.scripts.profiler.watch_and_kill"
    )

    await _main(options)

    # Ensure the profiler and watch and kill functions are called by
    # asyncio.gather
    mock_profile.assert_called_once()
    mock_watch_and_kill.assert_called_once()


# The cgroup layout of a PBS job on a node running cgroups in systemd
# "hybrid" mode: the resource controllers are on v1, and the v2 (unified)
# hierarchy only tracks the batch system's service.
HYBRID_PROC_CGROUP = """10:perf_event:/
9:cpuset:/pbspro.service/jobid/2761065.ehz100
8:freezer:/
7:memory:/pbspro.service/jobid/2761065.ehz100
6:pids:/system.slice/pbs.service
5:devices:/system.slice/pbs.service
4:cpu,cpuacct:/pbspro.service/jobid/2761065.ehz100
3:blkio:/system.slice/pbs.service
2:net_cls:/
1:name=systemd:/pbspro.service/jobid/2761065.ehz100
0::/system.slice/pbs.service
"""
# a malformed line, which should be skipped rather than blow up
HYBRID_PROC_CGROUP_JUNK = HYBRID_PROC_CGROUP + 'sad trombone\n'


def test_get_cgroup_names(mocker, monkeypatch):
    """It should map each controller to the cgroup this process is in."""
    monkeypatch.delenv('profiler_test_env_var', raising=False)
    mocker.patch.object(
        Path, 'read_text', return_value=HYBRID_PROC_CGROUP_JUNK
    )
    names = get_cgroup_names()

    job = 'pbspro.service/jobid/2761065.ehz100'
    # the controllers which matter are resolved independently
    assert names['memory'] == job
    assert names['cpu'] == job
    assert names['cpuacct'] == job
    # the unified hierarchy is stored separately, and here points at the
    # batch system's service rather than the job
    assert names['v2'] == 'system.slice/pbs.service'
    # other controllers are picked up too
    assert names['pids'] == 'system.slice/pbs.service'
    assert names['freezer'] == ''
    # "name=systemd" is a named hierarchy, not a controller
    assert 'name=systemd' not in names
    assert 'systemd' not in names


def test_get_cgroup_names_test_env_var(monkeypatch):
    """It should allow the functional tests to inject a cgroup name."""
    monkeypatch.setenv('profiler_test_env_var', '/test/cgroup/name')
    assert get_cgroup_names() == {
        'v2': 'test/cgroup/name',
        'memory': 'test/cgroup/name',
        'cpu': 'test/cgroup/name',
        'cpuacct': 'test/cgroup/name',
    }
    # the legacy single-name lookup uses it as well
    assert get_cgroup_name() == '/test/cgroup/name'


def test_get_cgroup_names_file_not_found(mocker, monkeypatch):
    """It should raise if /proc/<pid>/cgroup cannot be read."""
    monkeypatch.delenv('profiler_test_env_var', raising=False)
    mocker.patch.object(Path, 'read_text', side_effect=OSError('nope'))
    with pytest.raises(CylcProfilerError) as excinfo:
        get_cgroup_names()
    assert '/cgroup not found' in str(excinfo.value)


def test_v2_controllers_enabled(tmp_path):
    """It should detect a v2 hierarchy with no controllers enabled."""
    # a real v2 hierarchy
    enabled = tmp_path / 'enabled'
    enabled.mkdir()
    (enabled / 'cgroup.controllers').write_text('cpuset cpu io memory pids')
    assert v2_controllers_enabled(enabled) is True

    # systemd "hybrid" mode: process tracking only
    empty = tmp_path / 'empty'
    empty.mkdir()
    (empty / 'cgroup.controllers').write_text('\n')
    assert v2_controllers_enabled(empty) is False

    # not a cgroup v2 directory at all
    assert v2_controllers_enabled(tmp_path / 'does_not_exist') is False


def test_parse_memory_file_no_data(tmp_path):
    """It should return None if the stat file has no usage line in it."""
    stat_file = tmp_path / 'memory.stat'
    stat_file.write_text('pgfault 1234\npgmajfault 56\n')

    for version in (1, 2):
        process = Process(
            cgroup_memory_path=stat_file,
            cgroup_cpu_path='',
            memory_allocated_path=tmp_path,
            memory_version=version,
            cpu_version=version,
            max_rss=0)
        assert parse_memory_file(process) is None


def test_parse_cpu_file_empty(tmp_path):
    """It should raise if the cpu file exists but holds no usage data."""
    empty_file = tmp_path / 'cpu.stat'
    empty_file.write_text('')

    for version in (1, 2):
        process = Process(
            cgroup_memory_path='',
            cgroup_cpu_path=empty_file,
            memory_allocated_path=tmp_path,
            memory_version=version,
            cpu_version=version,
            max_rss=0)
        with pytest.raises(CylcProfilerError) as excinfo:
            parse_cpu_file(process)
        assert 'Unable to find cpu usage data' in str(excinfo.value)


def test_parse_cpu_file_unknown_version(tmp_path):
    """It should return 0 if the cgroup version is not one it handles."""
    process = Process(
        cgroup_memory_path='',
        cgroup_cpu_path=tmp_path / 'cpu.stat',
        memory_allocated_path=tmp_path,
        memory_version=3,
        cpu_version=3,
        max_rss=0)
    assert parse_cpu_file(process) == 0


def test_parse_memory_allocated_bad_data(tmp_path):
    """It should raise if a memory limit file cannot be parsed."""
    # cgroups v2
    v2_dir = tmp_path / 'v2'
    v2_dir.mkdir()
    (v2_dir / 'memory.max').write_text('Enter Sandman')
    v2_process = Process(
        cgroup_memory_path='',
        cgroup_cpu_path='',
        memory_allocated_path=v2_dir,
        memory_version=2,
        cpu_version=2,
        max_rss=0)
    with pytest.raises(CylcProfilerError) as excinfo:
        parse_memory_allocated(v2_process)
    assert 'Unable to find memory allocation' in str(excinfo.value)

    # cgroups v1
    v1_dir = tmp_path / 'v1'
    v1_dir.mkdir()
    (v1_dir / 'memory.limit_in_bytes').write_text('Off to never never land')
    v1_process = Process(
        cgroup_memory_path='',
        cgroup_cpu_path='',
        memory_allocated_path=v1_dir,
        memory_version=1,
        cpu_version=1,
        max_rss=0)
    with pytest.raises(CylcProfilerError) as excinfo:
        parse_memory_allocated(v1_process)
    assert 'Unable to find memory allocation' in str(excinfo.value)


def test_parse_memory_allocated_walk_limit(tmp_path):
    """It should give up walking up the tree rather than loop forever.

    Every cgroup from the leaf upwards is unlimited, and the tree is deeper
    than the number of levels the search is willing to climb.
    """
    for version, filename, unlimited in (
        (2, 'memory.max', 'max'),
        (1, 'memory.limit_in_bytes', '9223372036854771712'),
    ):
        leaf = tmp_path / f'deep{version}'
        leaf.mkdir()
        for depth in range(15):
            leaf = leaf / f'level_{depth}'
            leaf.mkdir()
        # write the "no limit" value at every level
        directory = leaf
        while directory != tmp_path:
            (directory / filename).write_text(unlimited)
            directory = directory.parent

        process = Process(
            cgroup_memory_path='',
            cgroup_cpu_path='',
            memory_allocated_path=leaf,
            memory_version=version,
            cpu_version=version,
            max_rss=0)
        assert parse_memory_allocated(process) == 0


def test_get_option_parser():
    """It should provide the profiler's CLI options."""
    parser = get_option_parser()
    options, args = parser.parse_args(
        ['-i', 'PT5S', '-m', '/sys/fs/cgroup']
    )
    assert args == []
    assert options.delay == 'PT5S'
    assert options.cgroup_location == '/sys/fs/cgroup'
    # comms=True, so the comms timeout option is available too
    assert hasattr(options, 'comms_timeout')


def test_main_cli(mocker):
    """It should parse the CLI options and run the profiler."""
    calls = []

    async def fake_main(options):
        calls.append(options)

    mocker.patch('cylc.flow.scripts.profiler._main', fake_main)
    main('-i', 'PT5S', '-m', '/sys/fs/cgroup')

    assert len(calls) == 1
    assert calls[0].delay == 'PT5S'
    assert calls[0].cgroup_location == '/sys/fs/cgroup'


def test_main_cancelled(mocker):
    """It should exit quietly if the profiler is cancelled."""
    async def fake_main(options):
        raise asyncio.CancelledError()

    mocker.patch('cylc.flow.scripts.profiler._main', fake_main)
    # should not raise
    main('-i', 'PT5S', '-m', '/sys/fs/cgroup')


def test_main_logs_errors(mocker, log_filter, caplog):
    """It should log, rather than raise, profiler errors.

    Profiling problems must never fail the job.
    """
    async def fake_main(options):
        raise CylcProfilerError(FileNotFoundError(), 'Cgroup not found')

    mocker.patch('cylc.flow.scripts.profiler._main', fake_main)
    with caplog.at_level(logging.INFO, logger=CYLC_LOG):
        main('-i', 'PT5S', '-m', '/sys/fs/cgroup')
    assert log_filter(contains='Cgroup not found', level=logging.INFO)
