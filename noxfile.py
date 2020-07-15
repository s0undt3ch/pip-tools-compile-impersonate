# -*- coding: utf-8 -*-
'''
noxfile
~~~~~~~

Nox configuration script
'''

# Import Python libs
from __future__ import absolute_import, unicode_literals, print_function
import sys

if __name__ == '__main__':
    sys.stderr.write('Do not execute this file directly. Use nox instead, it will know how to handle this file\n')
    sys.stderr.flush()
    exit(1)

# Import 3rd-party libs
import nox

PYTHON_VERSIONS = ('3.5', '3.6', '3.7', '3.8', '3.9')

# Nox options
#  Reuse existing virtualenvs
nox.options.reuse_existing_virtualenvs = True
#  Don't fail on missing interpreters
nox.options.error_on_missing_interpreters = False

@nox.session(python=PYTHON_VERSIONS)
def tests(session):
    session.run('python', '-m', 'pip', 'install', '.')
    session.install('pytest')
    session.run('pytest', '-ra', '-s', '-vv', 'tests', *session.posargs)


@nox.session(python=False, name='tests-system')
def tests_system(session):
    session.run('python', '-m', 'pip', 'install', '-e', '.')
    session.run('python', '-m', 'pip', 'install', 'pytest')
    session.run('python', '-m', 'pytest', '-ra', '-s', '-vv', 'tests', *session.posargs)
