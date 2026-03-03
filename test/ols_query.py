#!/usr/bin/env python3
"""
OpenShift Lightspeed Query Utility

Query OpenShift Lightspeed API (streaming mode).

Environment variables:
  OLS_BASE_URL - Lightspeed API URL
  OLS_TOKEN - Authentication token (default: from 'oc whoami -t')

Usage:
  ols_query.py "How to check PTP status?"
  ols_query.py "What is a pod?"
"""

import argparse
import json
import os
import subprocess
import sys
import textwrap
import requests

# Disable SSL warnings
requests.packages.urllib3.disable_warnings()

def print_wrapped(text, width=75):
    """Print text wrapped to specified width."""
    text = text.replace('**', '').replace('\\n', '\n').rstrip()

    # Handle markdown headers
    if text.startswith('#'):
        print(flush=True)
        header = text.lstrip('#').strip()
        print(f'\033[1m{header}\033[0m', flush=True)
        print(flush=True)
        return

    for l in text.split('\n'):
        if len(l) <= width:
            print(l)
        else:
            for w in textwrap.wrap(
                l,
                width=width,
                break_long_words=False,
                break_on_hyphens=False
            ):
                print(w, flush=True)

def stream_lightspeed(query_text):
    """Query OpenShift Lightspeed API (streaming). Yields response lines."""
    token = (
        os.getenv('OLS_TOKEN') or
        subprocess.check_output(['oc', 'whoami', '-t']).decode().strip()
    )

    try:
        response = requests.post(
            os.getenv('OLS_BASE_URL') + "/v1/streaming_query",
            headers={ "Authorization": f"Bearer {token}", "Content-Type": "application/json" },
            json={ "query": query_text, "conversation_id": None },
            stream=True,
            verify=False
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"API request failed: {e}", file=sys.stderr)
        sys.exit(1)

    return response.iter_lines()

def query_lightspeed(query_text, raw=False):
    """Query OpenShift Lightspeed API and print results."""
    lines = []
    for l0 in stream_lightspeed(query_text):
        line = l0.decode('utf-8')
        if not raw:
            if line.strip() == '---':
                break
            if line.startswith('Tool call:') or line.startswith('Tool result:'):
                continue
            #if not l0:
            #    continue
        if raw:
            print(line, flush=True)
        else:
            print_wrapped(line)
        lines.append(line)
    return '\n'.join(lines)

def main():
    parser = argparse.ArgumentParser(
        description='Query OpenShift Lightspeed API (streaming)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "How to check PTP status?"
  %(prog)s "What is a pod?"

  OLS_BASE_URL=https://... %(prog)s "Your question"
        """)

    parser.add_argument('query', help='Question to ask Lightspeed')
    parser.add_argument('-r', '--raw', action='store_true',
                        help='Output raw response without formatting')

    args = parser.parse_args()

    query_lightspeed(args.query, raw=args.raw)

if __name__ == "__main__":
    main()
