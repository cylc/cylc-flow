#!/usr/bin/env python
# coding=utf-8

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA & British Crown (Met Office) & Contributors.
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

import sys
from glob import glob
from os import environ
from os.path import join, dirname, realpath

from setuptools import setup, find_packages
# Monkey patching to disable version normalization, as we are using dates with
# leading zeroes
# https://github.com/pypa/setuptools/issues/308
from setuptools.extern.packaging import version as v

v.Version = v.LegacyVersion


def get_cylc_version():
    """Get Cylc version."""
    dir_path = dirname(realpath(__file__))
    module_path = join(dir_path, "lib")
    sys.path.append(module_path)
    # TODO: Cylc __init__.py changes PYTHONPATH, breaking setup.py
    previous_path = sys.path
    from cylc import version

    sys.path = previous_path
    environ["PYTHONPATH"] = ""
    return version.CYLC_VERSION


install_requires = [
    'colorama==0.4.1',
    'isodatetime==1!2.0.0',
    'jinja2==2.10',
    'markupsafe==1.1.1',
    'python-jose==3.0.1',
    'pyzmq==18.0.1'
]
tests_require = [
    'codecov',
    'coverage',
    'pytest-cov',
    'pytest',
    'pycodestyle',
    'virtualenv',
    'tox-travis'
]

extra_requires = {
    'empy': ['EmPy'],
    'all': []
}
extra_requires['all'] += extra_requires['empy']
extra_requires['all'] += tests_require

setup(
    version=get_cylc_version(),
    long_description=open('README.md').read(),
    long_description_content_type="text/markdown",
    scripts=glob(join('bin', '*')),
    packages=find_packages("lib/") + ["Jinja2Filters"],
    package_dir={"": "lib"},
    package_data={
        '': ['*.txt', '*.md', '*.sh']
    },
    include_package_data=False,
    install_requires=install_requires,
    tests_require=tests_require,
    extras_require=extra_requires,
    project_urls={
        "Documentation": "https://cylc.github.io/documentation.html",
        "Source": "https://github.com/cylc/cylc",
        "Tracker": "https://github.com/cylc/cylc/issues"
    }
)
