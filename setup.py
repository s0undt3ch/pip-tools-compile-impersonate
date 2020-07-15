#import re
#import sys
from setuptools import find_packages, setup
#from distutils import sysconfig
#site_packages_path = sysconfig.get_python_lib()
#try:
#    sprem = re.match(
#        r'.*(lib[\\/](python\d(\.\d)*[\\/])?site-packages)', site_packages_path, re.I)
#    if sprem is None:
#        sprem = re.match(
#            r'.*(lib[\\/](python\d(\.\d)*[\\/])?dist-packages)', site_packages_path, re.I)
#    rel_site_packages = sprem.group(1)
#except Exception as exc:
#    print("I'm having trouble finding your site-packages directory.  Is it where you expect?")
#    print("sysconfig.get_python_lib() returns '{}'".format(site_packages_path))
#    print("Exception was: {}".format(exc))
#    sys.exit(-1)

setup(
    name='pip-tools-compile',
    version='2.0',
    author="Pedro Algarvio",
    author_email="pedro@algarvio.me",
    maintainer="Pedro Algarvio",
    maintainer_email="pedro@algarvio.me",
    license="Apache Software License 2.0",
    #include_package_data=True,
    zip_safe=False,
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Testing",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Operating System :: OS Independent",
        "License :: OSI Approved :: Apache Software License",
    ],
    install_requires=[
        'pip-tools==4.5.0',
        'pip==19.1',
    ],
    packages=find_packages(),
    #data_files=[
        #(rel_site_packages, ["pip_tools_compile_hacks.pth"]),
        #(rel_site_packages, ["sitecustomize.py"])
    #],
    entry_points = {
        'console_scripts': ['pip-tools-compile=piptoolscompile.cli:main'],
    }
)
