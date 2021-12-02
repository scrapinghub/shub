from __future__ import absolute_import
import io
import os
from setuptools import setup, find_packages


about = {}
here = os.path.abspath(os.path.dirname(__file__))
with io.open(os.path.join(here, 'shub', '__init__.py'),
             mode='r', encoding='utf-8') as f:
    exec(f.read(), about)


setup(
    name='shub',
    version='3.0.0',
    packages=find_packages(exclude=('tests', 'tests.*')),
    url=about['DOCS_LINK'],
    description='Scrapinghub Command Line Client',
    long_description=open('README.rst').read(),
    author='Scrapinghub',
    author_email='info@scrapinghub.com',
    maintainer='Scrapinghub',
    maintainer_email='info@scrapinghub.com',
    license='BSD',
    entry_points={
        'console_scripts': ['shub = shub.tool:cli']
    },
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'click>=7.0',
        'docker',
        'pyyaml',
        'retrying',
        'requests',
        'scrapinghub>=2.3.1',
        'six>=1.7.0',
        'tqdm',
        'toml',
    ],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Operating System :: OS Independent',
        'Environment :: Console',
        'Topic :: Internet :: WWW/HTTP',
    ],
)
