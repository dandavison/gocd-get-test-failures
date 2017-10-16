"""
GoCD credentials must be stored as shell environment variables:

  export GOCD_USER=my_username GOCD_PASSWORD=my_password

Usage:
  gocd-get-test-failures BUILD [--format=FORMAT] [--stage=STAGE] [--job=JOB]
  gocd-get-test-failures --show-pipelines

Example:
  export GOCD_USER=my_username GOCD_PASSWORD=my_password
  gocd-get-test-failures some-pipeline/2275

Options:
  --format=FORMAT   Output format: 'html', 'json', 'md', or 'org'  [default: html].
  --show-pipelines  Show stage/job names for known pipelines.
  --stage=STAGE     Set stage name for pipeline.
  --job=JOB         Set job name for pipeline.
  -h --help         Show this help.
"""
from __future__ import print_function
from __future__ import unicode_literals

import asyncio
import json
import itertools
import os
import re
import sys
import warnings
from operator import itemgetter

import aiohttp
import lxml.etree
import markdown
import requests
import toolz
from docopt import docopt
from requests.packages.urllib3.exceptions import InsecureRequestWarning


requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

GOCD_HOST = os.getenv('GOCD_HOST')
PIPELINES = {}


ARGUMENTS = None


def main():

    global ARGUMENTS
    ARGUMENTS = docopt(__doc__)

    if ARGUMENTS['--show-pipelines']:
        print(json.dumps(PIPELINES, sort_keys=True, indent=2))
        sys.exit(0)

    if ARGUMENTS['--format'] not in {'html', 'json', 'markdown', 'md', 'org'}:
        raise ValueError('Invalid output format: %s' % arguments['--format'])

    if not (os.getenv('GOCD_USER') and os.getenv('GOCD_PASSWORD')):
        usage()

    failures = get_test_failures(ARGUMENTS['BUILD'])
    print(format_test_failures(failures, ARGUMENTS['--format']))


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


def format_test_failures(failures, output_format):
    failures = sorted(failures, key=itemgetter('test'))
    by_test_class = itertools.groupby(failures, itemgetter('test_class'))

    if output_format == 'json':
        return json.dumps(failures, sort_keys=True, indent=2)

    if output_format in {'md', 'markdown'}:
        lines = []
        for test_class, failures in by_test_class:
            lines.append('### ' + test_class)
            for failure in failures:
                lines.append('#### ' + failure['test'])
                lines.append('```\n' + failure['traceback'].strip() + '\n```')
        return '\n'.join(lines)

    elif output_format == 'org':
        lines = []
        for test_class, failures in by_test_class:
            lines.append('* ' + test_class)
            for failure in failures:
                lines.append('** ' + failure['test'])
                lines.append(failure['traceback'])
        return '\n'.join(lines)

    elif output_format == 'html':
        return markdown.markdown(
            format_test_failures(failures, 'md'),
            extensions=['fenced_code'],
        )

    else:
        raise ValueError('Invalid output format: %s' % output_format)


def _get_all_nosetest_xmls(build):
    """
    Return list of nosetest XMLs for all runs (until first 404 is encountered).
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

    # URLs are of the form /something/anotherthing/<run>

    # We do not know the set of valid URLs. I.e., we do not know the maximum
    # valid value of `run` after which all URLs will be 404s.  Instead, we keep
    # trying increasing values of `run` until we start getting 404s. Since we
    # do not know the maximum valid value of run a priori, we cannot create
    # tasks for fetching all valid URLs. Instead we create an initial chunk of
    # tasks, run these concurrently, and then if we haven't started
    # encountering 404s, move on to the next chunk.
    xmls = []
    seen_404 = False

    async def get_xml(run):
        nonlocal context, seen_404
        context = dict(context, run=run)
        conn = aiohttp.TCPConnector(verify_ssl=False)
        async with aiohttp.ClientSession(connector=conn) as session:
            resp = await session.get(url.format(**context))
            if resp.status == 404:
                # We expect to see 404s eventually, but a 404 for the first
                # value of `run` probably means that something is wrong.
                assert run > 1, ('Unexpected 404: %s' %
                                 url.format(**dict(context, password='********')))
                seen_404 = True
            else:
                resp.raise_for_status()
                data = await resp.content.read()
                xmls.append(data)

    chunk_size = 30
    ioloop = asyncio.get_event_loop()
    for run_chunk in toolz.partition_all(chunk_size, itertools.count(1)):
        task = asyncio.wait([get_xml(run) for run in run_chunk])
        ioloop.run_until_complete(task)
        if seen_404:
            ioloop.close()
            break

    return xmls


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
