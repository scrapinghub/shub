from __future__ import absolute_import
from setuptools import setup


setup(
    name='shub',
    version='2.4.2',
    packages=['shub'],
    url='http://doc.scrapinghub.com/shub.html',
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
    install_requires=['click', 'hubstorage', 'pip', 'requests', 'PyYAML',
                      'scrapinghub', 'six', 'docker-py', 'retrying'],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Operating System :: OS Independent',
        'Environment :: Console',
        'Topic :: Internet :: WWW/HTTP',
    ],
)
