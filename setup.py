#!/usr/bin/env python
# coding=utf-8

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

import codecs
import re
from glob import glob
from os.path import join, dirname, abspath

from setuptools import setup, find_namespace_packages

here = abspath(dirname(__file__))


def read(*parts):
    with codecs.open(join(here, *parts), 'r') as fp:
        return fp.read()


def find_version(*file_paths):
    version_file = read(*file_paths)
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]",
                              version_file, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")


install_requires = [
    'aiofiles==0.5.*',
    'ansimarkup>=1.0.0',
    'colorama>=0.4,<=1',
    'click>=7.0',
    'graphene>=2.1,<3',
    'jinja2==2.11.*',
    'metomi-isodatetime>=1!2.0.2, <1!2.1.0',
    'protobuf==3.13.*',
    'pyuv==1.4.*',
    'pyzmq==19.0.*',
    'psutil>=5.6.0',
    'urwid==2.*',
    'packaging'
]
tests_require = [
    'async-timeout>=3.0.0',
    'async_generator',
    'codecov>=2.0.0',
    'coverage>=5.0.0',
    'flake8>=3.0.0',
    'pycodestyle>=2.5.0',
    'pytest-asyncio>=0.14.0',
    'pytest-cov>=2.8.0',
    'pytest-xdist>=2',
    'pytest>=6',
    'testfixtures>=6.11.0'
]

extra_requires = {
    'empy': [
        'EmPy==3.3.*'
    ],
    'all': [],
    'report-timings': [
        'pandas==1.*'
    ],
    'main_loop-log_data_store': [
        'pympler',
        'matplotlib'
    ],
    'main_loop-log_main_loop': [
        'matplotlib'
    ],
    'main_loop-log_memory': [
        'pympler',
        'matplotlib'
    ]
}
extra_requires['all'] = (
    tests_require
    + list({
        req
        for reqs in extra_requires.values()
        for req in reqs
    })
)


setup(
    version=find_version("cylc", "flow", "__init__.py"),
    long_description=open('README.md').read(),
    long_description_content_type="text/markdown",
    scripts=glob(join('bin', '*')),
    packages=find_namespace_packages(include=["cylc.*"]),
    package_data={
        'cylc.flow': [
            'etc/*.yaml', 'etc/flow*.eg', 'etc/job.sh',
            'etc/syntax/*', 'etc/cylc-bash-completion'
        ]
    },
    install_requires=install_requires,
    tests_require=tests_require,
    extras_require=extra_requires,
    project_urls={
        "Documentation": "https://cylc.github.io/documentation.html",
        "Source": "https://github.com/cylc/cylc-flow",
        "Tracker": "https://github.com/cylc/cylc-flow/issues"
    }
)
