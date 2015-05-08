from setuptools import setup


setup(
    name='test_project',
    version='1.2.0',
    packages=['test_project'],
    url='https://doc.scrapinghub.com/test_project.html',
    description='Test Project',
    author='Scrapinghub',
    author_email='info@scrapinghub.com',
    maintainer='Scrapinghub',
    maintainer_email='info@scrapinghub.com',
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
