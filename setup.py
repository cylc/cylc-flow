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
    'jinja2==2.10',
    'markupsafe==1.0',
    'isodatetime==2018.11.0'
]
tests_require = [
    'mock',
    'codecov',
    'coverage',
    'pytest-cov',
    'pytest',
    'pycodestyle',
    'virtualenv',
    'tox-travis'
]

extra_requires = {
    'ssl': ['pyopenssl', 'requests'],
    'empy': ['EmPy'],
    'all': []
}
extra_requires['all'] += extra_requires['ssl']
extra_requires['all'] += extra_requires['empy']

setup(
    name="cylc",
    version=get_cylc_version(),
    description="Cylc (\"silk\") is a workflow engine for cycling systems - "
                "it orchestrates distributed suites of interdependent "
                "cycling tasks that may continue to run indefinitely.",
    long_description=open('README.md').read(),
    long_description_content_type="text/markdown",
    keywords=["scheduling", "forecast"],
    author="Hilary Oliver",
    author_email="cylc@googlegroups.com",
    url="https://cylc.github.io/cylc/",
    packages=find_packages("lib/") + ["Jinja2Filters"] +
             ['cylc/cylc-review/static/'] +
             ['cylc/cylc-review/static/css/'] +
             ['cylc/cylc-review/static/fonts/'] +
             ['cylc/cylc-review/static/images/'] +
             ['cylc/cylc-review/static/img/'] +
             ['cylc/cylc-review/static/js/'] +
             ['cylc/cylc-review/template/'],
    package_dir={"": "lib"},
    scripts=glob(join('bin', '*')),
    license="GPL",
    platforms="any",
    package_data={
        '': ['*.txt', '*.md', '*.html', '*.js', '*.css', '*.png', '*.jpg',
             '*.gif', '*.svg', '*.eot', '*.ttf', '*.woff', '*.woff2', '*.sh']
    },
    include_package_data=False,
    python_requires=">=2.7, <3",
    setup_requires=['pytest-runner'],
    install_requires=install_requires,
    tests_require=tests_require,
    extras_require=extra_requires,
    classifiers=[
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: License :: OSI Approved :: "
        "GNU General Public License v3 (GPLv3)",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2",
    ],
    project_urls={
        "Documentation": "https://cylc.github.io/cylc/documentation.html",
        "Source": "https://github.com/cylc/cylc",
        "Tracker": "https://github.com/cylc/cylc/issues"
    }
)
