from setuptools import find_packages
from setuptools import setup


setup(
    name='gocd-get-test-failures',
    author='Dan Davison',
    author_email='dan@counsyl.com',
    description="A command-line tool to fetch test output from GoCD",
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    entry_points={
        'console_scripts': [
            'gocd-get-test-failures = gocd_get_test_failures:main',
        ],
    },
)
