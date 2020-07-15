#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
    pip-tools-compile
    ~~~~~~~~~~~~~~~~~

    Wrapper around pip-tools to "impersonate" different distributions when compiling requirements
'''

# Import Python Libs
import io
import os
import re
import sys
import logging
import argparse
import platform
import tempfile
import textwrap
import traceback
try:
    from unittest import mock
except ImportError:
    import mock

CAPTURE_OUTPUT = os.environ.get('CAPTURE_OUTPUT', '1') == '1'

LOG_STREAM = io.StringIO()
logging.basicConfig(
    level=logging.DEBUG,
    stream=LOG_STREAM,
    datefmt='%H:%M:%S',
    format='%(asctime)s,%(msecs)03.0f [%(name)-5s:%(lineno)-4d][%(levelname)-8s] %(message)s')

# Import pip-tools Libs
# Keep a reference to the original DependencyCache class
from piptools.cache import DependencyCache

# Import pip libs
# We don't need Py2 vs Py3 encode/decode issues from pip
import pip._internal.utils.misc
real_version_info = sys.version_info

log = logging.getLogger(os.path.basename(__file__))


def tweak_piptools_depcache_filename(version_info, platform, *args, **kwargs):
    depcache = DependencyCache(*args, **kwargs)
    cache_file = os.path.join(os.path.dirname(depcache._cache_file),
                              'depcache-{}-py{}.{}.json'.format(platform, *version_info))
    log.info('Tweaking the pip-tools depcache file to: %s', cache_file)
    depcache._cache_file = cache_file
    return depcache


class CatureSTDs(object):

    def __init__(self):
        self._stdout = io.StringIO()
        self._stderr = io.StringIO()
        self._sys_stdout = sys.stdout
        self._sys_stderr = sys.stderr

    def __enter__(self):
        sys.stdout = self._stdout
        sys.stderr = self._stderr
        return self

    def __exit__(self, *args):
        sys.stdout = self._sys_stdout
        sys.stderr = self._sys_stderr
        if not CAPTURE_OUTPUT:
            self._stdout.seek(0)
            sys.stdout.write(self._stdout.read())
            self._stderr.seek(0)
            sys.stderr.write(self._stderr.read())

    @property
    def stdout(self):
        self._stdout.seek(0)
        return self._stdout.read()

    @property
    def stderr(self):
        self._stderr.seek(0)
        return self._stderr.read()


def compile_requirement_file(source, dest, options, unknown_args):
    log.info('Compiling requirements to %s', dest)

    input_rewrites  = {}
    passthrough_lines = {}

    regexes = []
    for regex in options.passthrough_line_from_input:
        regexes.append(re.compile(regex))

    call_args = ['pip-compile', '-o', dest]
    if unknown_args:
        call_args += unknown_args
    if options.include:
        includes = []
        for input_file in options.include:
            out_contents = []
            input_file = input_file.format(py_version=options.py_version)
            with open(input_file) as rfh:
                in_contents = rfh.read()
                for line in in_contents.splitlines():
                    match_found = False
                    for regex in regexes:
                        if match_found:
                            break
                        if regex.match(line):
                            match_found = True
                            if input_file not in input_rewrites:
                                temp_reqs_file = tempfile.NamedTemporaryFile(delete=False)
                                temp_reqs_file.close()
                                input_rewrites[input_file] = temp_reqs_file.name
                            if input_file not in passthrough_lines:
                                passthrough_lines[input_file] = []
                    if match_found:
                        passthrough_lines[input_file].append(line)
                        # Skip this line
                        continue
                    out_contents.append(line)
            if input_file in input_rewrites:
                with open(input_rewrites[input_file], 'w') as wfh:
                    for line in out_contents:
                        wfh.write('{}\n'.format(line))
                includes.append(input_rewrites[input_file])
            else:
                includes.append(input_file)
        call_args += includes
    call_args.append(source)

    original_sys_arg = sys.argv[:]
    with mock.patch('pip._internal.utils.misc.sys.version_info',
                    new_callable=mock.PropertyMock(return_value=real_version_info)):
        try:
            print('Running: {}'.format(' '.join(call_args)))
            print('  Impersonating: {}'.format(options.platform))
            print('  Mocked Python Version: {}'.format(options.py_version))
            sys.argv = call_args[:]
            log.debug('Switching sys.argv to: %s', sys.argv)
            try:
                import piptools.scripts.compile
                piptools.scripts.compile.cli()
            except SystemExit as exc:
                if exc.code == 0:
                    return True
                print('Failed to compile requirements. Exit code: {}'.format(exc.code))
                return False
            except Exception:
                print('Exception raised when processing {}'.format(source))
                print(traceback.format_exc())
                return False
        finally:
            log.info('Finished compiling %s', dest)

            if input_rewrites:
                with open(dest) as rfh:
                    dest_contents = rfh.read()

                for input_file, rewriten_file in input_rewrites.items():
                    if rewriten_file in dest_contents:
                        dest_contents = dest_contents.replace(rewriten_file, input_file)

                    try:
                        os.unlink(rewriten_file)
                    except OSError:
                        pass

                with open(dest, 'w') as wfh:
                    wfh.write(dest_contents)
                    for input_file, lines in passthrough_lines.items():
                        wfh.write('# Passthrough dependencies from {}\n'.format(input_file))
                        for line in lines:
                            wfh.write('{}\n'.format(line))

            sys.argv = original_sys_arg

    # Flag success
    return True


def show_info_to_patch():
    import pprint
    import platform
    print('Generating information under {}\n'.format(platform.system()))
    patch_data = (
        ('pip._internal.pep425tags', 'get_impl_version_info'),
        ('pip._internal.utils.packaging', 'sys.version_info'),
        ('pip._vendor.packaging.markers', 'platform.python_version'),
        ('pip._internal.pep425tags', 'get_platform'),
        ('pip._internal.pep425tags', 'get_supported'),
        ('pip._internal.index', 'get_supported'),
        ('pip._vendor.packaging.markers', 'os.name'),
        ('pip._vendor.packaging.markers', 'sys.platform'),
        ('pip._vendor.packaging.markers', 'platform.machine'),
        ('pip._vendor.packaging.markers', 'platform.release'),
        ('pip._vendor.packaging.markers', 'platform.system'),
        ('pip._vendor.packaging.markers', 'platform.version'),
        )
    real_data = {}
    for module, function in patch_data:
        if module not in real_data:
            real_data[module] = {}
        mod = __import__(module)
        mod_parts = module.split('.')
        mod_parts.pop(0)
        while mod_parts:
            part = mod_parts.pop(0)
            mod = getattr(mod, part)
        func_parts = function.split('.')
        func = mod
        while func_parts:
            part = func_parts.pop(0)
            func = getattr(func, part)
        data = func
        if callable(data):
            data = data()
        real_data[module][function] = data

    pprint.pprint(real_data)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--show-info-to-patch',
        action='store_true',
        help='Print out the information we require to patch the multiple platforms'
    )
    parser.add_argument(
        '--platform',
        choices=('windows', 'darwin', 'linux'),
        default=platform.system().lower()
    )
    parser.add_argument('--py-version', default='{}.{}'.format(*sys.version_info))
    parser.add_argument('--include', action='append', default=[])
    parser.add_argument('--output-dir', default=None)
    parser.add_argument('--out-prefix', default=None)
    parser.add_argument(
        '--remove-line', default=[], action='append',
        help='Python regular experession to search and remove from the compiled requirements and remove it'
    )
    parser.add_argument(
        '--passthrough-line-from-input', default=[], action='append',
        help='Python regular experession to search and remove from the input requirements and append in the destination requirements file'
    )
    parser.add_argument('files', nargs='*')

    options, unknown_args = parser.parse_known_args()

    if options.show_info_to_patch:
        show_info_to_patch()
        parser.exit(0)

    if not options.files:
        parser.exit(2, 'Please pass at least one requirement file')

    import piptoolscompile.hacks
    impersonations = piptoolscompile.hacks.IMPERSONATIONS

    regexes = []
    for regex in options.remove_line:
        regexes.append(re.compile(regex))

    stdout = stderr = None
    exitcode = 0

    with CatureSTDs() as capstds:
        with impersonations[options.platform](options.py_version, options.platform):
            import piptools.scripts.compile
            for fpath in options.files:
                if not fpath.endswith('.in'):
                    continue

                # Return the log strem to 0, either to write a log file in case of an error,
                # or to overwrite the contents for this next fpath
                LOG_STREAM.seek(0)

                source_dir = os.path.dirname(fpath)
                if options.output_dir:
                    dest_dir = options.output_dir
                else:
                    dest_dir = os.path.join(source_dir, 'py{}'.format(options.py_version))
                if not os.path.isdir(dest_dir):
                    os.makedirs(dest_dir)
                outfile = os.path.basename(fpath).replace('.in', '.txt')
                if options.out_prefix:
                    outfile = '{}-{}'.format(options.out_prefix, outfile)
                outfile_path = os.path.join(dest_dir, outfile)
                if not compile_requirement_file(fpath, outfile_path, options, unknown_args):
                    exitcode = 1
                    error_logfile = outfile_path.replace('.txt', '.log')
                    with open(error_logfile, 'w') as wfh:
                        wfh.write(LOG_STREAM.read())
                        LOG_STREAM.seek(0)
                        print('Error log file at {}'.format(error_logfile))
                    continue

                if not regexes:
                    continue

                with open(outfile_path, 'r') as rfh:
                    in_contents = rfh.read()

                out_contents = []
                for line in in_contents.splitlines():
                    print('Processing line: {!r} // {}'.format(line, [r.pattern for r in regexes]))
                    for regex in regexes:
                        if regex.match(line):
                            print("Line commented out by regex '{}': '{}'".format(regex.pattern, line))
                            line = textwrap.dedent('''\
                                # Next line explicitly commented out by {} because of the following regex: '{}'
                                # {}'''.format(
                                    os.path.basename(__file__),
                                    regex.pattern,
                                    line
                                )
                            )
                            break
                    out_contents.append(line)

                with open(outfile_path, 'w') as wfh:
                    wfh.write(os.linesep.join(out_contents) + os.linesep)

            if exitcode:
                stdout = capstds.stdout
                stderr = capstds.stderr

    if stdout:
        sys.__stdout__.write(capstds.stdout)
    if stderr:
        sys.__stderr__.write(capstds.stderr)
    sys.exit(exitcode)


if __name__ == '__main__':
    main()
