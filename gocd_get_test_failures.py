"""
GoCD credentials must be stored as shell environment variables:

  export GOCD_USER=my_username GOCD_PASSWORD=my_password

Usage:
  gocd-get-test-failures BUILD [--format=FORMAT] [--stage=STAGE] [--job=JOB]
  gocd-get-test-failures --show-pipelines

Example:
  export GOCD_USER=my_username GOCD_PASSWORD=my_password
  gocd-get-test-failures dev-website-ci-5/2275

Options:
  --format=FORMAT   Output format: org or json [default: org].
  --show-pipelines  Show stage/job names for known pipelines.
  --stage=STAGE     Set stage name for pipeline.
  --job=JOB         Set job name for pipeline.
  -h --help         Show this help.
"""
from __future__ import print_function
from __future__ import unicode_literals

import json
import itertools
import os
import re
import sys
import warnings
from operator import itemgetter

import lxml.etree
import requests
from docopt import docopt
from requests.packages.urllib3.exceptions import InsecureRequestWarning


requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

GOCD_HOST = os.getenv('GOCD_HOST') or 'go-cd.counsyl.com'
PIPELINES = {
    'dev-website-ci': {
        'stage': 'test',
        'job': 'unit',
    },
    'dev-website-all': {
        'stage': 'lengthy-tests',
        'job': 'lengthy',
    },
}


ARGUMENTS = None


def main():

    global ARGUMENTS
    ARGUMENTS = docopt(__doc__)

    if ARGUMENTS['--show-pipelines']:
        print(json.dumps(PIPELINES, sort_keys=True, indent=2))
        sys.exit(0)

    if ARGUMENTS['--format'] not in {'json', 'org'}:
        raise ValueError('Invalid output format: %s' % arguments['--format'])

    if not (os.getenv('GOCD_USER') and os.getenv('GOCD_PASSWORD')):
        usage()

    failures = get_test_failures(ARGUMENTS['BUILD'])
    print_test_failures(failures, ARGUMENTS['--format'])


def usage():
    sys.argv = [sys.argv[0], '--help']
    docopt(__doc__)


def get_test_failures(build):
    """
    Return list of test failure dicts.
    """
    failures = []
    for xml in _get_all_nosetest_xmls(build):
        root = lxml.etree.fromstring(xml)
        failures.extend(_get_failures(root))

    return failures


def print_test_failures(failures, output_format):
    failures = sorted(failures, key=itemgetter('test'))
    if output_format == 'json':
        print(json.dumps(failures, sort_keys=True, indent=2))
    elif output_format == 'org':
        by_test_class = itertools.groupby(failures, itemgetter('test_class'))
        for test_class, failures in by_test_class:
            print('* ' + test_class)
            for failure in failures:
                print('** ' + failure['test'])
                print(failure['traceback'])
    else:
        raise ValueError('Invalid output format: %s' % output_format)


def _get_all_nosetest_xmls(build):
    """
    Generator yielding nosetest XML for all runs (until first 404 is encountered).
    """
    run_path = '{build}/{stage}/1/{job}-runInstance-{run}'
    url = ('https://{user}:{password}@{host}/go/files/' +
           run_path +
           '/test-results/nosetests.xml')

    context = {
        'host': GOCD_HOST,
        'user': os.getenv('GOCD_USER'),
        'password': os.getenv('GOCD_PASSWORD'),
        'build': build,
    }

    context.update(_get_pipeline_data(build))

    assert context['user'], 'Missing environment variable GOCD_USER'
    assert context['password'], 'Missing environment variable GOCD_PASSWORD'

    for run in itertools.count(1):
        context['run'] = run
        print(run_path.format(**context), file=sys.stderr)
        resp = requests.get(url.format(**context), verify=False)
        if resp.status_code == 404:
            context['password'] = '********'
            assert run > 1, '404 for first run URL: %s' % url.format(**context)
            raise StopIteration
        else:
            resp.raise_for_status()
            yield resp.content


def _get_pipeline_data(build):
    match = re.match('(.+)-\d+', build)
    assert match, 'Unsupported pipeline: %s' % build
    pipeline, = match.groups()
    try:
        return PIPELINES[pipeline]
    except KeyError:
        pipeline = {
            'stage': ARGUMENTS['--stage'],
            'job': ARGUMENTS['--job'],
        }
        if all(pipeline.values()):
            return pipeline
        else:
            raise ValueError(
                'Unsupported pipeline: %s\n '
                'See --show-pipelines; '
                'you may be able to use the --stage and --job options '
                'to fetch test failures from an unsupported pipeline.'
                % build
            )


def _get_failures(root):
    """
    Generator yielding a dict for each error element in the XML.
    """
    for testcase in root.getchildren():
        for error in testcase.findall('error'):
            yield {
                'test': testcase.attrib['name'],
                'test_class': testcase.attrib['classname'],
                'traceback': error.text,
            }


if __name__ == '__main__':
    main()
