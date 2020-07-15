import os
import sys
import functools
import logging
from collections import namedtuple
try:
    from unittest import mock
except ImportError:
    import mock

# Import pip-tools Libs
# Keep a reference to the original DependencyCache class
from piptools.cache import DependencyCache

# Import pip libs
# We don't need Py2 vs Py3 encode/decode issues from pip
import pip._internal.utils.misc
real_version_info = sys.version_info

# Let's import get_supported because we need the returned value from the un-mocked function
from pip._internal.pep425tags import get_supported

log = logging.getLogger(__name__)

version_info = namedtuple('version_info', ['major', 'minor', 'micro', 'releaselevel', 'serial'])


class ImpersonateSystem(object):

    __slots__ = ('_python_version', '_python_version_info', '_platform')

    def __init__(self, python_version_info, platform):
        self._python_version = python_version_info
        parts = [int(part) for part in python_version_info.split('.') if part.isdigit()]
        python_version_info = list(sys.version_info)
        for idx, part in enumerate(parts):
            python_version_info[idx] = part
        python_version_info = version_info(*python_version_info)
        self._python_version_info = python_version_info
        self._platform = platform

    def get_mocks(self):
        yield mock.patch('pip._internal.utils.misc.sys.version_info',
                         new_callable=mock.PropertyMock(return_value=real_version_info))
        yield mock.patch('piptools.scripts.compile.DependencyCache',
                         wraps=functools.partial(tweak_piptools_depcache_filename,
                                                 self._python_version_info,
                                                 self._platform))
        yield mock.patch('pip._internal.pep425tags.get_impl_version_info',
                         return_value=self._python_version_info[:2])
        yield mock.patch('pip._internal.utils.packaging.sys.version_info',
                         new_callable=mock.PropertyMock(return_value=self._python_version_info))
        yield mock.patch('pip._vendor.packaging.markers.platform.python_version',
                         return_value='{}.{}.{}'.format(*self._python_version_info))

    def get_global_mocks(self):
        raise StopIteration

    def __enter__(self):
        os.environ["IMPERSONATE_PLATFORM"] = self._platform
        os.environ["IMPERSONATE_PY_VERSION"] = self._python_version
        for mock_obj in self.get_mocks():
            mock_obj.start()
        return self

    def __exit__(self, *args):
        os.environ.pop("IMPERSONATE_PLATFORM")
        os.environ.pop("IMPERSONATE_PY_VERSION")
        mock.patch.stopall()


def get_supported_with_fixed_unicode_width(*args, **kwargs):
    supported = get_supported(*args, **kwargs)
    for version, abi, arch in supported[:]:
        if abi.endswith('u'):
            supported.append((version, abi[:-1], arch))
    return supported


def tweak_piptools_depcache_filename(version_info, platform, *args, **kwargs):
    depcache = DependencyCache(*args, **kwargs)
    cache_file = os.path.join(os.path.dirname(depcache._cache_file),
                              'depcache-{}-py{}.{}.json'.format(platform, *version_info))
    log.info('Tweaking the pip-tools depcache file to: %s', cache_file)
    depcache._cache_file = cache_file
    return depcache


class ImpersonateWindows(ImpersonateSystem):

    def get_mocks(self):
        for entry in super(ImpersonateWindows, self).get_mocks():
            yield entry
        # We don't want pip trying query python's internals, it knows how to mock that internal information
        yield mock.patch('pip._internal.pep425tags.get_config_var', return_value=None)
        # Impersonate Windows 32
        yield mock.patch('pip._internal.pep425tags.get_platform', return_value='win32')
        # Wrap get_supported in out own function call to fix unicode width issues
        yield mock.patch('pip._internal.pep425tags.get_supported', wraps=get_supported_with_fixed_unicode_width)
        yield mock.patch('pip._internal.index.get_supported', wraps=get_supported_with_fixed_unicode_width)
        # Patch pip's vendored packaging markers
        yield mock.patch('pip._vendor.packaging.markers.os.name', new_callable=mock.PropertyMock(return_value='nt'))
        yield mock.patch('pip._vendor.packaging.markers.sys.platform', new_callable=mock.PropertyMock(return_value='win32'))
        yield mock.patch('pip._vendor.packaging.markers.platform.machine', return_value='AMD64')
        yield mock.patch('pip._vendor.packaging.markers.platform.release', return_value='8.1')
        yield mock.patch('pip._vendor.packaging.markers.platform.system', return_value='Windows')
        yield mock.patch('pip._vendor.packaging.markers.platform.version', return_value='6.3.9600')


class ImpersonateDarwin(ImpersonateSystem):

    class PlistLibModuleMock:

        def readPlist(self, fpath):
            return self.load(fpath)

        def load(self, fpath):
            if fpath != '/System/Library/CoreServices/SystemVersion.plist':
                raise RuntimeError(
                    'PlistLibModuleMock.load does not know how to handle {!r}'.format(fpath)
                )
            return {
                'ProductBuildVersion': '19D76',
                'ProductCopyright': '1983-2020 Apple Inc.',
                'ProductName': 'Mac OS X',
                'ProductUserVisibleVersion': '10.15.3',
                'ProductVersion': '10.15.3',
                'iOSSupportVersion': '13.0'
            }

    def get_mocks(self):
        for entry in super(ImpersonateDarwin, self).get_mocks():
            yield entry
        # We don't want pip trying query python's internals, it knows how to mock that internal information
        yield mock.patch('pip._internal.pep425tags.get_config_var', return_value=None)
        # Impersonate Windows 32
        yield mock.patch('pip._internal.pep425tags.get_platform', return_value='macosx_10_15_x86_64')
        # Wrap get_supported in out own function call to fix unicode width issues
        yield mock.patch('pip._internal.pep425tags.get_supported', wraps=get_supported_with_fixed_unicode_width)
        yield mock.patch('pip._internal.index.get_supported', wraps=get_supported_with_fixed_unicode_width)
        # Patch pip's vendored packaging markers
        yield mock.patch('pip._vendor.packaging.markers.os.name', new_callable=mock.PropertyMock(return_value='posix'))
        yield mock.patch('pip._vendor.packaging.markers.sys.platform', new_callable=mock.PropertyMock(return_value='darwin'))
        yield mock.patch('pip._vendor.packaging.markers.platform.machine', return_value='x86_64')
        yield mock.patch('pip._vendor.packaging.markers.platform.release', return_value='19.3.0')
        yield mock.patch('pip._vendor.packaging.markers.platform.system', return_value='Darwin')
        yield mock.patch('pip._vendor.packaging.markers.platform.version',
                         return_value='Darwin Kernel Version 19.3.0: Thu Jan  9 20:58:23 PST 2020; root:xnu-6153.81.5~1/RELEASE_X86_64')
        yield mock.patch('pip._vendor.packaging.markers.platform.python_version', return_value='{}.{}.{}'.format(*self._python_version_info))

    def get_global_mocks(self):
        #yield mock.patch('sys.platform', new_callable=mock.PropertyMock(return_value='darwin'))
        yield mock.patch.dict('sys.modules', plistlib=ImpersonateDarwin.PlistLibModuleMock())


class ImpersonateLinux(ImpersonateSystem):

    def get_mocks(self):
        for entry in super(ImpersonateLinux, self).get_mocks():
            yield entry
        # We don't want pip trying query python's internals, it knows how to mock that internal information
        yield mock.patch('pip._internal.pep425tags.get_config_var', return_value=None)
        # Impersonate Windows 32
        yield mock.patch('pip._internal.pep425tags.get_platform', return_value='linux2')
        # Wrap get_supported in out own function call to fix unicode width issues
        yield mock.patch('pip._internal.pep425tags.get_supported', wraps=get_supported_with_fixed_unicode_width)
        yield mock.patch('pip._internal.index.get_supported', wraps=get_supported_with_fixed_unicode_width)
        # Patch pip's vendored packaging markers
        yield mock.patch('pip._vendor.packaging.markers.sys.platform',
                         new_callable=mock.PropertyMock(return_value='linux{}'.format('2' if self._python_version_info[0] == 2 else '')))
        yield mock.patch('pip._vendor.packaging.markers.os.name', new_callable=mock.PropertyMock(return_value='posix'))
        yield mock.patch('pip._vendor.packaging.markers.platform.machine', return_value='x86_64')
        yield mock.patch('pip._vendor.packaging.markers.platform.release', return_value='4.19.29-1-lts')
        yield mock.patch('pip._vendor.packaging.markers.platform.system', return_value='Linux')
        yield mock.patch('pip._vendor.packaging.markers.platform.version', return_value='#1 SMP Thu Mar 14 15:39:08 CET 2019')
        yield mock.patch('pip._vendor.packaging.markers.platform.python_version', return_value='{}.{}.{}'.format(*self._python_version_info))

IMPERSONATIONS = {
    'darwin': ImpersonateDarwin,
    'windows': ImpersonateWindows,
    'linux': ImpersonateLinux
}


if 'IMPERSONATE_PY_VERSION' in os.environ and 'IMPERSONATE_PLATFORM' in os.environ:

    import atexit

    platform = os.environ['IMPERSONATE_PLATFORM']
    py_version = os.environ['IMPERSONATE_PY_VERSION']
    impersonation = IMPERSONATIONS[platform](py_version, platform)
    for patch in impersonation.get_global_mocks():
        patch.start()
    atexit.register(mock.patch.stopall)
