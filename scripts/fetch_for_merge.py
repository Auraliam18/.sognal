"""Bounded publication fetch for Actions shallow checkouts.

Default fetch after a depth=1 checkout can download the entire missing ledger
history. Fetch at most the recent day, then require a real common ancestor.
Never reset, force-push, drop local commits, or ignore a failed fetch.
"""
import argparse
import subprocess
from datetime import datetime, timedelta, timezone


def fetch(branch, cwd=None):
    if branch not in ('main', 'gh-pages'):
        raise ValueError('unsupported publication branch')
    since=(datetime.now(timezone.utc)-timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
    cmd=['git','fetch','--no-tags','--no-recurse-submodules',f'--shallow-since={since}',
         'origin',f'+refs/heads/{branch}:refs/remotes/origin/{branch}']
    subprocess.run(cmd,cwd=cwd,timeout=180,check=True)
    subprocess.run(['git','merge-base','HEAD',f'origin/{branch}'],cwd=cwd,timeout=10,check=True)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('branch',choices=['main','gh-pages'])
    fetch(p.parse_args().branch)
