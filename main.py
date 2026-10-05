import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import requests
from rich import Console, Table

from cache import cache_get, cache_set, open_cache
from complexity import EXT_TO_LANGUAGE, analyze_directory, analyze_sources
from copilot import generate_suggestions
from github_client import GithubClient, GithubError
from report import render_markdown

WORKDIR = Path('.cache')
REPORT_DIR = Path('reports')
console = Console()


def clone_repo(owner, repo, commit_sha):
    target = WORKDIR / repo
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if shutil.which('git'):
        try:
            subprocess.run(['git', 'clone', '--depth', '1', f'https://github.com/{owner}/{repo}.git', str(target)],
                           check=True, capture_output=True, timeout=300)
            sha = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=target, check=True,
                                 capture_output=True, text=True, timeout=30).stdout.strip()
            return target, sha
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
            if target.exists():
                shutil.rmtree(target)
            console.print(f'[yellow]Git clone failed, using tarball fallback: {exc}[/yellow]')
    try:
        response = requests.get(f'https://codeload.github.com/{owner}/{repo}/tar.gz/{commit_sha}', timeout=120)
    except requests.RequestException as exc:
        raise RuntimeError(f'GitHub tarball download failed: {exc}') from exc
    if response.status_code != 200:
        raise RuntimeError('GitHub tarball download failed')
    with tarfile.open(fileobj=io.BytesIO(response.content), mode='r:gz') as archive:
        archive.extractall(target)
    top = next(iter(target.iterdir()), None)
    return (top, commit_sha) if top and top.is_dir() else (target, commit_sha)


def pull_request_sources(client, owner, repo, number):
    pr = client.get_pr(owner, repo, number)
    head_sha = pr['head']['sha']
    files = client.get_pr_files(owner, repo, number)
    sources = []
    for item in files:
        path = item.get('filename')
        if not path or not EXT_TO_LANGUAGE.get(Path(path).suffix.lower()):
            continue
        try:
            source = client.get_raw_file(owner, repo, path, head_sha)
            sources.append((path, source))
        except GithubError:
            console.print(f'[yellow]Could not fetch {path}[/yellow]')
    return head_sha, sources


def analyze_repo(args):
    token = os.environ.get('GITHUB_TOKEN')
    client = GithubClient(token)
    repo_info = client.get_repo(args.owner, args.repo)
    if repo_info.get('private') and not token:
        raise GithubError('GITHUB_TOKEN is required for private repositories')
    api_languages = client.get_languages(args.owner, args.repo)
    if args.pr:
        commit_sha, sources = pull_request_sources(client, args.owner, args.repo, args.pr)
        data = analyze_sources(sources, commit_sha, args.max_files)
    else:
        commit_sha = client.get_latest_commit(args.owner, args.repo)
        root, local_sha = clone_repo(args.owner, args.repo, commit_sha)
        key = f'repo:{args.owner}/{args.repo}:{local_sha}'
        cache = open_cache('health_cache.sqlite')
        cached = cache_get(cache, key)
        if cached:
            data = json.loads(cached)
        else:
            data = analyze_directory(root, local_sha, args.max_files)
            cache_set(cache, key, json.dumps(data))
        cache.close()
    data['repo_info'] = repo_info
    data['api_languages'] = api_languages
    copilot_text = generate_suggestions(data, args.owner, args.repo, args.pr)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / f'{args.owner}_{args.repo}_health.md'
    report_path.write_text(render_markdown(data, copilot_text, args.pr), encoding='utf-8')
    print_results(data, copilot_text, report_path, commit_sha, args.pr)


def print_results(data, copilot_text, report_path, commit_sha, pr_number):
    summary = data.get('summary', {})
    console.rule('Health report ' + str(data.get('repo')))
    console.print(f'Commit: [bold]{commit_sha}[/bold]')
    if pr_number:
        console.print(f'Pull request: #{pr_number}')
    language_text = ', '.join(f'{key} {value}' for key, value in sorted((data.get('api_languages') or {}).items())) or str(data.get('repo'))
    console.print(f'Languages: {language_text}')
    console.print('Total functions: ' + str(summary.get('total_functions', 0)) +
                  '  Average complexity: ' + str(summary.get('avg_complexity', 0)))
    table = Table(title='Top functions')
    for column in ['Path', 'Function', 'Complexity', 'Nesting', 'Lines']:
        table.add_column(column)
    for item in data.get('top_functions', [])[:10]:
        table.add_row(item['path'], item['name'], str(item['complexity']), str(item['nesting_depth']), str(item['lines']))
    console.print(table)
    if copilot_text:
        console.rule('Copilot suggestions')
        console.print(copilot_text)
    else:
        console.print('[yellow]Copilot CLI was unavailable or returned no output.[/yellow]')
    console.print('Report saved to: ' + str(report_path))


def main():
    parser = argparse.ArgumentParser(description='Analyze a public GitHub repository with tree-sitter.')
    subparsers = parser.add_subparsers(dest='command', required=True)
    analyze = subparsers.add_parser('analyze', help='Analyze a repository or pull request')
    analyze.add_argument('--owner', required=True)
    analyze.add_argument('--repo', required=True)
    analyze.add_argument('--pr', type=int)
    analyze.add_argument('--max-files', type=int, default=200, dest='max_files')
    args = parser.parse_args()
    if args.command == 'analyze':
        return analyze_repo(args)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except GithubError as exc:
        console.print(f'[red]GitHub API error: {exc}[/red]')
        sys.exit(1)
    except (RuntimeError, OSError, json.JSONDecodeError) as exc:
        console.print(f'[red]Analysis failed: {exc}[/red]')
        sys.exit(1)
    except KeyboardInterrupt:
        console.print('[red]Interrupted[/red]')
        sys.exit(130)