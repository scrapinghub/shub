from setuptools import setup

setup(
    name='shub-image',
    version='0.2.4',
    packages=['shub_image'],
    description='Scrapinghub release tool',
    long_description=open('README.rst').read(),
    author='Scrapinghub',
    author_email='info@scrapinghub.com',
    maintainer='Scrapinghub',
    maintainer_email='info@scrapinghub.com',
    license='BSD',
    entry_points={
        'console_scripts': ['shub-image = shub_image.tool:cli']
    },
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'click',
        'requests',
        'six',
        'shub>=0.2.4',
        'docker-py',
    ],
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
    test_suite='tests',
    tests_require=['mock', 'pytest']
)
