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

import codecs
import re
from distutils.errors import DistutilsExecError
from glob import glob
from os.path import join, dirname, abspath
from shutil import move, rmtree

from setuptools import setup, find_packages
SPHINX_AVAILABLE = False
try:
    from sphinx.setup_command import BuildDoc
    SPHINX_AVAILABLE = True
except ImportError:
    pass

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


cmdclass = {}
if SPHINX_AVAILABLE:

    class MakeDocs(BuildDoc):
        """Port of old `cylc-make-docs`. Removed in #2989.

        This class extends the Sphinx command class for setuptools. With
        a difference that it tries to mimic the behaviour of the previous
        `cylc-make-docs`.

        So first it will execute `make-commands.sh`, which builds the
        commands help information, in the appendices.

        Then, instead of calling one builder, this class will call the
        builder fot he single HTML, and also the builder for the multiple
        HTML documentation.

        Finally, one more tweak in this class is to move the doctrees
        folder (in the same level as the documentation) to within the
        documentation folder, named `.doctrees`, as before with
        `cylc-make-docs`.
        """

        def run(self):  # type: () -> None
            try:
                self.spawn(["./doc/src/custom/make-commands.sh"])
            except DistutilsExecError as e:
                self.warn("Failed to run make-commands.sh")
                raise e
            self.do_run("html", "built-sphinx")
            self.do_run("singlehtml", "built-sphinx-single")

        def do_run(self, builder: str, output_dir: str):
            """
            Args:
                builder (str): name of the Sphinx builder
                output_dir (str): directory to write the documentation produced
            """
            self.builder = builder
            self.builder_target_dirs = [
                (builder, join(self.build_dir, output_dir))]
            super().run()
            # move doctrees to $build_dir/.doctrees
            correct_doctrees = join(self.builder_target_dirs[0][1],
                                    ".doctrees")
            rmtree(correct_doctrees, ignore_errors=True)
            move(self.doctree_dir, correct_doctrees)

    cmdclass["build_sphinx"] = MakeDocs


install_requires = [
    'colorama==0.4.*',
    'isodatetime==1!2.0.*',
    'jinja2>=2.10.1, <2.11.0',
    'markupsafe==1.1.*',
    'python-jose==3.0.*',
    'pyzmq==18.0.*'
]
tests_require = [
    'codecov==2.0.*',
    'coverage==4.5.*',
    'pytest-cov==2.6.*',
    'pytest==4.4.*',
    'pycodestyle==2.5.*',
    'testfixtures==6.6.*'
]

extra_requires = {
    'empy': ['EmPy==3.3.*'],
    'docs': ['sphinx==2.0.*'],
    'all': []
}
extra_requires['all'] += extra_requires['empy']
extra_requires['all'] += extra_requires['docs']
extra_requires['all'] += tests_require

setup(
    version=find_version("lib", "cylc", "__init__.py"),
    long_description=open('README.md').read(),
    long_description_content_type="text/markdown",
    scripts=glob(join('bin', '*')),
    packages=find_packages("lib/") + ["Jinja2Filters"],
    package_dir={"": "lib"},
    package_data={
        '': ['*.txt', '*.md', '*.sh']
    },
    cmdclass=cmdclass,
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
