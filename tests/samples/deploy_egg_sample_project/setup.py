from __future__ import absolute_import
from setuptools import setup


setup(
    name='test_project',
    version='1.2.0',
    packages=['test_project'],
    description='Test Project',
    author='Zyte',
    author_email='info@zyte.com',
    maintainer='Zyte',
    maintainer_email='info@zyte.com',
    license='BSD',
    include_package_data=True,
    zip_safe=False,
    install_requires=[],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Operating System :: OS Independent',
        'Environment :: Console',
        'Topic :: Internet :: WWW/HTTP',
    ],
)
