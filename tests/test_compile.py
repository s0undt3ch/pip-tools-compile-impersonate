# -*- coding: utf-8 -*-
'''
    test_compile
    ~~~~~~~~~~~~

    Test Static Compilation
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import sys
import shutil
import textwrap

# Import 3rd-party libs
import pytest

PYVER = '{}.{}'.format(*sys.version_info)
TARGET_PLATFORMS = ('linux', 'windows', 'darwin')
REPO_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
INPUT_REQUIREMENTS_DIR = os.path.relpath(os.path.join(os.path.dirname(__file__), 'files'), REPO_ROOT)
EXPECTED_REQUIREMENTS_DIR = os.path.relpath(os.path.join(os.path.dirname(__file__), 'files', 'expected'), REPO_ROOT)
TARGET_PYTHON_VERSIONS = (
    '3.5',
    '3.6',
    '3.7',
    '3.8',
    '3.9'
)

@pytest.mark.parametrize('python_version', TARGET_PYTHON_VERSIONS)
def test_py_version_nested_requirements(run_command, python_version):
    input_requirement = os.path.join(INPUT_REQUIREMENTS_DIR, 'boto3.in')
    compiled_requirements = os.path.join(INPUT_REQUIREMENTS_DIR, 'py{}'.format(python_version), 'boto3.txt')
    expected_requirements = os.path.join(EXPECTED_REQUIREMENTS_DIR, 'py{}'.format(python_version), 'boto3.txt')
    if os.path.exists(compiled_requirements):
        os.unlink(compiled_requirements)
    # Run it through pip-tools-compile
    retcode = run_command(
        'pip-tools-compile',
        '-v',
        '--py-version={}'.format(python_version),
        '--platform=linux',
        input_requirement
    )
    assert retcode == 0
    with open(compiled_requirements) as crfh:
        compiled_contents = crfh.read()
    with open(expected_requirements) as erfh:
        expected_contents = erfh.read()
    assert compiled_contents == expected_contents
    if python_version.startswith('2.'):
        assert 'futures' in compiled_contents, \
                'The future library was not found in the compiled output\n{}'.format(compiled_contents)
    else:
        assert 'futures' not in compiled_contents, \
                'The future library was found in the compiled output\n{}'.format(compiled_contents)


MARKERS_INPUT_REQUIREMENT_TPL = textwrap.dedent('''\
    boto3==1.9.121; {marker} == {values[0]}
    boto3==1.9.122; {marker} == {values[1]}
    boto3==1.9.123; {marker} == {values[2]}
    ''')
MARKERS = {
    'os.name': ['nt', '"posix" and platform_system != "Linux"', '"posix" and platform_system != "Darwin"'],
    'sys.platform': ['win32', 'darwin', 'linux{}'.format('2' if sys.version_info.major == 2 else '')],
    'platform_system': ['Windows', 'Darwin', 'Linux']}

@pytest.mark.parametrize(
    'platform,marker,expected',
    (
        ('windows', 'os.name', 'boto3==1.9.121'),
        ('darwin', 'os.name', 'boto3==1.9.122'),
        ('linux', 'os.name', 'boto3==1.9.123'),
        ('windows', 'sys.platform', 'boto3==1.9.121'),
        ('darwin', 'sys.platform', 'boto3==1.9.122'),
        ('linux', 'sys.platform', 'boto3==1.9.123'),
        ('windows', 'platform_system', 'boto3==1.9.121'),
        ('darwin', 'platform_system', 'boto3==1.9.122'),
        ('linux', 'platform_system', 'boto3==1.9.123'),
    ),
)
def test_markers(run_command, platform, marker, expected):
    input_requirement_name = 'boto3-markers'
    input_requirement = os.path.join(INPUT_REQUIREMENTS_DIR, '{}.in'.format(input_requirement_name))
    with open(input_requirement, 'w') as wfh:
        wfh.write(
            MARKERS_INPUT_REQUIREMENT_TPL.format(
                marker=marker,
                values=[
                    value if value.startswith('"') else '"{}"'.format(value)
                    for value in MARKERS[marker]
                ]
            )
        )
    compiled_requirements = os.path.join(
        INPUT_REQUIREMENTS_DIR,
        'py{}.{}'.format(*sys.version_info),
        '{}.txt'.format(input_requirement_name)
    )
    if os.path.exists(compiled_requirements):
        os.unlink(compiled_requirements)
    # Run it through pip-tools-compile
    retcode = run_command(
        'pip-tools-compile',
        '-v',
        '--platform={}'.format(platform),
        input_requirement
    )
    assert retcode == 0
    with open(compiled_requirements) as crfh:
        compiled_contents = crfh.read()
    assert expected in compiled_contents, \
            'The {!r} was not found in the compiled output\n{}'.format(expected, compiled_contents)


@pytest.mark.parametrize('platform', ['linux', 'darwin', 'windows'])
def test_pywin32(run_command, platform):
    '''
    pywin32 has been an issue when mocking the requirements file compilation. test it.
    '''
    if sys.version_info >= (3, 8):
        pytest.skip("Can't install pywin32 on windows yet?!")
    input_requirement_name = 'pywin32-req'
    input_requirement = os.path.join(INPUT_REQUIREMENTS_DIR, '{}.in'.format(input_requirement_name))
    with open(input_requirement, 'w') as wfh:
        wfh.write(textwrap.dedent('''\
            pep8
            pywin32==228; sys.platform == 'win32'
            '''
            )
        )
    compiled_requirements = os.path.join(
        INPUT_REQUIREMENTS_DIR,
        'py{}.{}'.format(*sys.version_info),
        '{}.txt'.format(input_requirement_name)
    )
    if os.path.exists(compiled_requirements):
        os.unlink(compiled_requirements)
    # Run it through pip-tools-compile
    retcode = run_command(
        'pip-tools-compile',
        '-v',
        '--platform={}'.format(platform),
        input_requirement
    )
    assert retcode == 0
    with open(compiled_requirements) as crfh:
        compiled_contents = crfh.read()
    if platform == 'windows':
        assert 'pywin32==' in compiled_contents, \
            'The pywin32 requirement was not found in the compiled output\n{}'.format(compiled_contents)
    else:
        assert 'pywin32==' not in compiled_contents, \
            'The pywin32 requirement was found in the compiled output\n{}'.format(compiled_contents)


@pytest.mark.parametrize('platform', ['linux', 'darwin', 'windows'])
def test_jsonschema(run_command, platform):
    '''
    jsonschema pulls in backports under py2, make sure that under py3 those don't end up in the final requirements
    '''
    input_requirement_name = 'jsonschema==2.6.0'
    input_requirement = os.path.join(INPUT_REQUIREMENTS_DIR, '{}.in'.format(input_requirement_name))
    with open(input_requirement, 'w') as wfh:
        wfh.write(input_requirement_name + '\n')
    compiled_requirements = os.path.join(
        INPUT_REQUIREMENTS_DIR,
        'py3.5',
        '{}.txt'.format(input_requirement_name)
    )
    if os.path.exists(compiled_requirements):
        os.unlink(compiled_requirements)
    # Run it through pip-tools-compile
    retcode = run_command(
        'pip-tools-compile',
        '-v',
        '--py-version=3.5',
        '--platform={}'.format(platform),
        input_requirement
    )
    assert retcode == 0
    with open(compiled_requirements) as crfh:
        compiled_contents = crfh.read()

    assert 'functools' not in compiled_contents


@pytest.mark.parametrize('platform', ['linux', 'darwin', 'windows'])
def test_pyobjc(run_command, platform):
    '''
    pyobjc has been an issue when mocking the requirements file compilation. test it.
    '''
    if not sys.platform.startswith('darwin') and platform == 'darwin' and (sys.version_info >= (3, 8) or sys.version_info < (3, 6)):
        pytest.skip("We have problems compiling pyobjc on {}.{}".format(*sys.version_info))
    input_requirement_name = 'pyobjc-req'
    input_requirement = os.path.join(INPUT_REQUIREMENTS_DIR, '{}.in'.format(input_requirement_name))
    if sys.version_info >= (3, 8):
        pyobjc_version = "5.2"
    else:
        pyobjc_version = "5.1"
    with open(input_requirement, 'w') as wfh:
        wfh.write(textwrap.dedent('''\
            pep8
            pyobjc=={}; sys.platform == 'darwin'
            '''.format(pyobjc_version)
            )
        )
    compiled_requirements = os.path.join(
        INPUT_REQUIREMENTS_DIR,
        'py{}.{}'.format(*sys.version_info),
        '{}.txt'.format(input_requirement_name)
    )
    if os.path.exists(compiled_requirements):
        os.unlink(compiled_requirements)
    # Run it through pip-tools-compile
    retcode = run_command(
        'pip-tools-compile',
        '-v',
        '--platform={}'.format(platform),
        input_requirement
    )
    assert retcode == 0
    with open(compiled_requirements) as crfh:
        compiled_contents = crfh.read()
    if platform == 'darwin':
        assert 'pyobjc==' in compiled_contents, \
            'The pyobjc requirement was not found in the compiled output\n{}'.format(compiled_contents)
    else:
        assert 'pyobjc==' not in compiled_contents, \
            'The pyobjc requirement was found in the compiled output\n{}'.format(compiled_contents)
