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
# Tests for functions contained in cylc.flow.job_file.
# TODO remove the unittest dependency - it should not be necessary.

from contextlib import suppress
import io
import os
from pathlib import Path
import pytest
from tempfile import NamedTemporaryFile
from textwrap import dedent

from cylc.flow import (
    __version__,
    __file__ as cylc_flow_file,
)
from cylc.flow.job_file import JobFileWriter
from cylc.flow.platforms import platform_from_name


@pytest.mark.parametrize(
    'in_value, out_value',
    [('~foo/bar bar', '~foo/"bar bar"'),
     ('~/bar bar', '~/"bar bar"'),
     ('~/a', '~/"a"'),
     ('test', '"test"'),
     ('~', '~'),
     ('~a', '~a'),
     ('foo%s', '"foo%s"'),
     ('foo%(i)d', '"foo3"')]
)
def test_get_variable_value_definition(in_value, out_value):
    """Test the value for single/tilde variables are correctly quoted, and
    parameter environment templates are handled"""
    param_dict = {'i': 3}
    res = JobFileWriter._get_variable_value_definition(in_value, param_dict)
    assert(out_value == res)


@pytest.fixture
def fixture_get_platform():
    """ Allows pytest to cache default platform dictionary.

    Args:
        custom_settings (dict):
            settings that you wish to override.

    Returns:
        platforms dictionary.
    """
    def inner_func(custom_settings=None):
        platform = platform_from_name()
        if custom_settings is not None:
            platform.update(custom_settings)
        return platform
    yield inner_func


def test_write(fixture_get_platform):
    """Test write function outputs jobscript file correctly."""
    with NamedTemporaryFile() as local_job_file_path:
        local_job_file_path = local_job_file_path.name
        platform = fixture_get_platform(
            {
                "job runner command template": "woof",
            }
        )
        job_conf = {
            "platform": platform,
            "task_id": "1/baa",
            "workflow_name": "farm_noises",
            "work_d": "farm_noises/work_d",
            "uuid_str": "neigh",
            'environment': {'cow': '~/moo',
                            'sheep': '~baa/baa',
                            'duck': '~quack'},
            "job_d": "1/baa/01",
            "try_num": 1,
            "flow_nums": {1},
            # "job_runner_name": "background",
            "param_var": {"duck": "quack",
                          "mouse": "squeak"},
            "execution_time_limit": "moo",
            "namespace_hierarchy": ["root", "baa", "moo"],
            "dependencies": ['moo', 'neigh', 'quack'],
            "init-script": "This is the init script",
            "env-script": "This is the env script",
            "err-script": "This is the err script",
            "pre-script": "This is the pre script",
            "script": "This is the script",
            "post-script": "This is the post script",
            "exit-script": "This is the exit script",
        }
        JobFileWriter().write(local_job_file_path, job_conf)

        assert (os.path.exists(local_job_file_path))
        size_of_file = os.stat(local_job_file_path).st_size
        # This test only needs to check that the file is created and is
        # non-empty as each section is covered by individual unit tests.
        assert(size_of_file > 10)

    """Test the header is correctly written"""

    expected = ('#!/bin/bash -l\n#\n# ++++ THIS IS A CYLC JOB SCRIPT '
                '++++\n# Workflow: farm_noises\n# Task: 1/baa\n# Job '
                'log directory: 1/baa/01\n# Job runner: '
                'background\n# Job runner command template: woof\n#'
                ' Execution time limit: moo')

    platform = fixture_get_platform(
        {"job runner command template": "woof"}
    )
    job_conf = {
        "platform": platform,
        "job runner": "background",
        "execution_time_limit": "moo",
        "workflow_name": "farm_noises",
        "task_id": "1/baa",
        "job_d": "1/baa/01"
    }

    with io.StringIO() as fake_file:
        JobFileWriter()._write_header(fake_file, job_conf)
        assert(fake_file.getvalue() == expected)


@pytest.mark.parametrize(
    'job_conf,expected',
    [
        (  # basic
            {
                "platform": {
                    "job runner": "loadleveler",
                    "job runner command template": "test_workflow",
                },
                "directives": {"moo": "foo",
                               "cluck": "bar"},
                "workflow_name": "farm_noises",
                "task_id": "1/baa",
                "job_d": "1/test_task_id/01",
                "job_file_path": "directory/job",
                "execution_time_limit": 60
            },
            ('\n\n# DIRECTIVES:\n# @ job_name = farm_noises.baa.1'
                '\n# @ output = directory/job.out\n# @ error = directory/'
                'job.err\n# @ wall_clock_limit = 120,60\n# @ moo = foo'
                '\n# @ cluck = bar\n# @ queue')

        ),
        (  # Check no directives is correctly written
            {
                "platform": {
                    "job runner": "slurm",
                    "job runner command template": "test_workflow"
                },
                "directives": {},
                "workflow_name": "farm_noises",
                "task_id": "1/baa",
                "job_d": "1/test_task_id/01",
                "job_file_path": "directory/job",
                "execution_time_limit": 60
            },
            (
                '\n\n# DIRECTIVES:\n#SBATCH '
                '--job-name=baa.1.farm_noises\n#SBATCH '
                '--output=directory/job.out\n#SBATCH --error=directory/'
                'job.err\n#SBATCH --time=1:00'
            )

        ),
        (  # Check pbs max job name length
            {
                "platform": {
                    "job runner": "pbs",
                    "job runner command template": "test_workflow",
                    "job name length maximum": 15
                },
                "directives": {},
                "workflow_name": "farm_noises",
                "task_id": "1/baaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "job_d": "1/test_task_id/01",
                "job_file_path": "directory/job",
                "execution_time_limit": 60
            },
            ('\n\n# DIRECTIVES:\n#PBS -N baaaaaaaaaaaaaa\n#PBS -o '
             'directory/job.out\n#PBS -e directory/job.err\n#PBS -l '
             'walltime=60')
        ),
        (  # Check sge directives are correctly written
            {
                "platform": {
                    "job runner": "sge",
                    "job runner command template": "test_workflow",
                },
                "directives": {"-V": "",
                               "-q": "queuename",
                               "-l": "s_vmem=1G,s_cpu=60"},
                "workflow_name": "farm_noises",
                "task_id": "1/baa",
                "job_d": "1/test_task_id/01",
                "job_file_path": "$HOME/directory/job",
                "execution_time_limit": 1000

            },
            ('\n\n# DIRECTIVES:\n#$ -N farm_noises.baa.1\n#$ -o directory/'
             'job.out\n#$ -e directory/job.err\n#$ -l h_rt=0:16:40\n#$ -V\n#'
             '$ -q queuename\n#$ -l s_vmem=1G,s_cpu=60'
             )
        )
    ], ids=["1", "2", "3", "4"])
def test_write_directives(fixture_get_platform, job_conf: dict, expected: str):
    """"Test the directives section of job script file is correctly
        written"""
    with io.StringIO() as fake_file:
        JobFileWriter()._write_directives(fake_file, job_conf)
        assert(fake_file.getvalue() == expected)


@pytest.mark.parametrize(
    "job_runner",
    ["at", "background", "loadleveler", "pbs", "sge", "slurm"])
def test_traps_for_each_job_runner(job_runner: str):
    """Test traps for each job runner"""
    platform = platform_from_name()
    platform.update({
        "job runner": f"{job_runner}",
    })
    job_conf = {
        "platform": platform,
        "directives": {},
        "workflow_name": 'test_traps_for_each_job_runner',
    }

    with io.StringIO() as fake_file:
        JobFileWriter()._write_prelude(fake_file, job_conf)
        output = fake_file.getvalue()
        assert("CYLC_FAIL_SIGNALS='EXIT ERR TERM XCPU" in output)


@pytest.mark.parametrize(
    'set_CYLC_ENV_NAME',
    [
        pytest.param(True, id='CYLC_ENV_NAME=True'),
        pytest.param(False, id='CYLC_ENV_NAME=False'),
    ]
)
def test_write_prelude(monkeypatch, fixture_get_platform, set_CYLC_ENV_NAME):
    """Test the prelude section of job script file is correctly
    written.
    """
    if set_CYLC_ENV_NAME:
        monkeypatch.setenv('CYLC_ENV_NAME', 'myenv')
    else:
        with suppress(KeyError):
            monkeypatch.delenv('CYLC_ENV_NAME')

    monkeypatch.setattr('cylc.flow.flags.verbosity', 2)
    expected = ('\nCYLC_FAIL_SIGNALS=\'EXIT ERR TERM XCPU\'\n'
                'CYLC_VACATION_SIGNALS=\'USR1\'\nexport PATH=moo/baa:$PATH'
                '\nexport CYLC_VERBOSE=true'
                '\nexport CYLC_DEBUG=true'
                f'\nexport CYLC_VERSION=\'{__version__}\'')
    if set_CYLC_ENV_NAME:
        expected += '\nexport CYLC_ENV_NAME=\'myenv\''
    expected += '\nexport CYLC_WORKFLOW_ID="test_write_prelude"'
    expected += '\nexport CYLC_WORKFLOW_INITIAL_CYCLE_POINT=\'20200101T0000Z\''
    job_conf = {
        "workflow_name": "test_write_prelude",
        "platform": fixture_get_platform({
            "job runner": "loadleveler",
            "job runner command template": "test_workflow",
            "host": "localhost",
            "copyable environment variables": [
                "CYLC_WORKFLOW_INITIAL_CYCLE_POINT"
            ],
            "cylc path": "moo/baa"
        }),
        "directives": {"restart": "yes"},
    }
    monkeypatch.setenv("CYLC_WORKFLOW_INITIAL_CYCLE_POINT", "20200101T0000Z")
    monkeypatch.setenv("CYLC_WORKFLOW_NAME", "test_write_prelude")
    monkeypatch.setenv("CYLC_WORKFLOW_NAME_BASE", "test_write_prelude")

    with io.StringIO() as fake_file:
        # copyable environment variables
        JobFileWriter()._write_prelude(fake_file, job_conf)
        assert(fake_file.getvalue() == expected)


def test_write_workflow_environment(fixture_get_platform, monkeypatch):
    """Test workflow environment is correctly written in jobscript"""
    # set some workflow environment conditions
    monkeypatch.setattr('cylc.flow.flags.verbosity', 2)
    workflow_env = {'CYLC_UTC': 'True',
                    'CYLC_CYCLING_MODE': 'integer',
                    'CYLC_WORKFLOW_NAME': 'blargh/quack',
                    'CYLC_WORKFLOW_NAME_BASE': 'quack'}
    job_file_writer = JobFileWriter()
    job_file_writer.set_workflow_env(workflow_env)
    # workflow env not correctly setting...check this
    expected = ('\n\ncylc__job__inst__cylc_env() {\n    # CYLC WORKFLOW '
                'ENVIRONMENT:\n    export CYLC_CYCLING_MODE="integer"\n  '
                '  export CYLC_UTC="True"'
                '\n    export CYLC_WORKFLOW_NAME="blargh/quack"'
                '\n    export CYLC_WORKFLOW_NAME_BASE="quack"'
                '\n    export TZ="UTC"'
                '\n    export CYLC_WORKFLOW_UUID="neigh"')
    job_conf = {
        "platform": fixture_get_platform({
            "host": "localhost",
        }),
        "workflow_name": "farm_noises",
        "uuid_str": "neigh"
    }
    with io.StringIO() as fake_file:
        job_file_writer._write_workflow_environment(fake_file, job_conf)
        result = fake_file.getvalue()
        assert result == expected


def test_write_script():
    """Test script is correctly written in jobscript"""

    expected = (
        "\n\ncylc__job__inst__init_script() {\n# INIT-SCRIPT:\n"
        "This is the init script\n}\n\ncylc__job__inst__env_script()"
        " {\n# ENV-SCRIPT:\nThis is the env script\n}\n\n"
        "cylc__job__inst__err_script() {\n# ERR-SCRIPT:\nThis is the err "
        "script\n}\n\ncylc__job__inst__pre_script() {\n# PRE-SCRIPT:\n"
        "This is the pre script\n}\n\ncylc__job__inst__script() {\n"
        "# SCRIPT:\nThis is the script\n}\n\ncylc__job__inst__post_script"
        "() {\n# POST-SCRIPT:\nThis is the post script\n}\n\n"
        "cylc__job__inst__exit_script() {\n# EXIT-SCRIPT:\n"
        "This is the exit script\n}")

    job_conf = {
        "init-script": "This is the init script",
        "env-script": "This is the env script",
        "err-script": "This is the err script",
        "pre-script": "This is the pre script",
        "script": "This is the script",
        "post-script": "This is the post script",
        "exit-script": "This is the exit script",
        "workflow_name": "test_write_script",
    }

    with io.StringIO() as fake_file:
        JobFileWriter()._write_script(fake_file, job_conf)
        assert(fake_file.getvalue() == expected)


def test_no_script_section_with_comment_only_script():
    """Test jobfilewriter does not generate script section when script is
        comment only"""
    expected = ("")

    job_conf = {
        "init-script": "",
        "env-script": "",
        "err-script": "",
        "pre-script": "#This is the pre script/n #moo /n#baa",
        "script": "",
        "post-script": "",
        "exit-script": "",
        "workflow_name": "test_no_script_section_with_comment_only_script"
    }

    with io.StringIO() as fake_file:

        JobFileWriter()._write_script(fake_file, job_conf)
        blah = fake_file.getvalue()
        print(blah)
        assert(fake_file.getvalue() == expected)


def test_write_task_environment():
    """Test task environment is correctly written in jobscript"""
    # set some task environment conditions
    expected = ('\n\n    # CYLC TASK ENVIRONMENT:\n    '
                'export CYLC_TASK_COMMS_METHOD=ssh\n    '
                'export CYLC_TASK_JOB="1/moo/01"\n    export '
                'CYLC_TASK_NAMESPACE_HIERARCHY="baa moo"\n    export '
                'CYLC_TASK_DEPENDENCIES="moo neigh quack"\n    export '
                'CYLC_TASK_TRY_NUMBER=1\n    export '
                'CYLC_TASK_FLOW_NUMBERS=1\n    export '
                'CYLC_TASK_PARAM_duck="quack"\n    export '
                'CYLC_TASK_PARAM_mouse="squeak"\n    '
                'CYLC_TASK_WORK_DIR_BASE=\'farm_noises/work_d\'\n}')
    job_conf = {
        "platform": {'communication method': 'ssh'},
        "job_d": "1/moo/01",
        "namespace_hierarchy": ["baa", "moo"],
        "dependencies": ['moo', 'neigh', 'quack'],
        "try_num": 1,
        "flow_nums": {1},
        "param_var": {"duck": "quack",
                      "mouse": "squeak"},
        "work_d": "farm_noises/work_d",
        "workflow_name": "test_write_task_environment",
    }
    with io.StringIO() as fake_file:
        JobFileWriter()._write_task_environment(fake_file, job_conf)
        assert(fake_file.getvalue() == expected)


def test_write_runtime_environment():
    """Test runtime environment is correctly written in jobscript"""

    expected = (
        '\n\ncylc__job__inst__user_env() {\n    # TASK RUNTIME '
        'ENVIRONMENT:\n    export cow sheep duck\n'
        '    cow=~/"moo"\n    sheep=~baa/"baa"\n    '
        'duck=~quack\n}')
    job_conf = {
        'environment': {
            'cow': '~/moo',
            'sheep': '~baa/baa',
            'duck': '~quack'
        },
        "workflow_name": "test_write_runtime_environment",
    }
    with io.StringIO() as fake_file:
        JobFileWriter()._write_runtime_environment(fake_file, job_conf)
        assert(fake_file.getvalue() == expected)


def test_write_epilogue():
    """Test epilogue is correctly written in jobscript"""
    expected = '\n' + dedent('''
        CYLC_RUN_DIR="${CYLC_RUN_DIR:-$HOME/cylc-run}"
        . "${CYLC_RUN_DIR}/${CYLC_WORKFLOW_ID}/.service/etc/job.sh"
        cylc__job__main

        #EOF: 1/moo/01
    ''')
    job_conf = {'job_d': "1/moo/01"}
    with io.StringIO() as fake_file:
        JobFileWriter()._write_epilogue(fake_file, job_conf)
        assert(fake_file.getvalue() == expected)


def test_write_global_init_scripts(fixture_get_platform):
    """Test global init script is correctly written in jobscript"""

    job_conf = {
        "platform": fixture_get_platform({
            "global init-script": (
                'export COW=moo\n'
                'export PIG=oink\n'
                'export DONKEY=HEEHAW\n'
            )
        })
    }
    expected = '\n' + dedent('''
        # GLOBAL INIT-SCRIPT:
        export COW=moo
        export PIG=oink
        export DONKEY=HEEHAW
    ''')
    with io.StringIO() as fake_file:
        JobFileWriter()._write_global_init_script(fake_file, job_conf)
        assert(fake_file.getvalue() == expected)


def test_homeless_platform(fixture_get_platform):
    """Ensure there are no uses of $HOME before the global init-script.

    This is to allow users to configure a $HOME on machines with no $HOME
    directory.
    """
    job_conf = {
        "platform": fixture_get_platform({
            'global init-script': 'some-script'
        }),
        "task_id": "1/a",
        "workflow_name": "b",
        "work_d": "c/d",
        "uuid_str": "e",
        'environment': {},
        'cow': '~/moo',
        "job_d": "1/a/01",
        "try_num": 1,
        "flow_nums": {1},
        # "job_runner_name": "background",
        "param_var": {},
        "execution_time_limit": None,
        "namespace_hierarchy": [],
        "dependencies": [],
        "init-script": "",
        "env-script": "",
        "err-script": "",
        "pre-script": "",
        "script": "",
        "post-script": "",
        "exit-script": "",
    }

    with NamedTemporaryFile() as local_job_file_path:
        local_job_file_path = local_job_file_path.name
        JobFileWriter().write(local_job_file_path, job_conf)
        with open(local_job_file_path, 'r') as local_job_file:
            job_script = local_job_file.read()

    # ensure that $HOME is not used before the global init-script
    for line in job_script.splitlines():
        if line.startswith(' '):
            # ignore env/script functions which aren't run until later
            continue
        if line == '# GLOBAL INIT-SCRIPT:':
            # quit once we've hit the global init-script
            break
        if 'HOME' in line:
            # bail if $HOME is used
            raise Exception(f'$HOME found in {line}\n{job_script}')

    # also ensure there is no use of $HOME in the job.sh script
    with open(Path(cylc_flow_file).parent / 'etc/job.sh', 'r') as job_sh:
        job_sh_txt = job_sh.read()
        if 'HOME' in job_sh_txt:
            raise Exception('$HOME found in job.sh\n{job_sh_txt}')
