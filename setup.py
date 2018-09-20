#!/usr/bin/env python
# coding=utf-8

from distutils.core import setup

setup(name='cylc',
    version='8.0',
    description='Cylc ("silk") is a workflow engine for cycling systems - it \
    orchestrates distributed suites of interdependent cycling tasks that may continue to run indefinitely.',
    author='Cylc',
    author_email='cylc@googlegroups.com',
    url='https://cylc.github.io/cylc/',
    packages=['lib/cylc'],
    license='GPL',
    platforms='any',
    install_requires=['jinja2=2.10', 'markupsafe=1.0', 'cherrypy=18.0.1'],
    python_requires='>=2.7'
)
