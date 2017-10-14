from setuptools import find_packages
from setuptools import setup


with open('./requirements.txt') as fp:
    requirements = [line.strip() for line in fp]

setup(
    name='gocd-get-test-failures',
    author='Dan Davison',
    author_email='dan@counsyl.com',
    description="A command-line tool to fetch test output from GoCD",
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=requirements,
    entry_points={
        'console_scripts': [
            'gocd-get-test-failures = gocd_get_test_failures:main',
        ],
    },
)
