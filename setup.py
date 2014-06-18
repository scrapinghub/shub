setup_args = {
    'name': 'shub',
    'version': '1.0',
    'packages': ['shub'],
    'url': 'https://doc.scrapinghub.com/shub.html',
    'description': 'Scrapinghub Command Line Client',
    'long_description': open('README.rst').read(),
    'author': 'Scrapinghub',
    'author_email': 'info@scrapinghub.com',
    'maintainer': 'Scrapinghub',
    'maintainer_email': 'info@scrapinghub.com',
    'license': 'BSD',
    'scripts': ['bin/shub'],
    'install_requires': ['click'],
    'classifiers': [
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
}


from setuptools import setup
setup(**setup_args)
