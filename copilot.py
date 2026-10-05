import os
import shutil
import subprocess


def _prompt(data, owner, repo, pr_number=None):
    functions = data.get('top_functions', [])[:5]
    if not functions:
        return None
    lines = [f'Repository: {owner}/{repo}']
    if pr_number:
        lines.append(f'Pull request: #{pr_number}')
    lines.append('Summarize refactor risks and suggest concrete next steps for the functions below:')
    for item in functions:
        lines.append('- ' + str(item['path']) + ' :: ' + str(item['name']) +
                     ' complexity=' + str(item['complexity']) + ' nesting=' + str(item['nesting_depth']))
    return '\n'.join(lines)


def generate_suggestions(data, owner, repo, pr_number=None):
    prompt = _prompt(data, owner, repo, pr_number)
    if not prompt:
        return None

    target = None
    args = []
    copilot_bin = os.environ.get('COPILOT_CLI_BIN') or shutil.which('copilot')
    if copilot_bin:
        target = copilot_bin
        args = ['--prompt', prompt]
    else:
        gh_bin = shutil.which('gh')
        if not gh_bin:
            return None
        target = gh_bin
        args = ['copilot', '--prompt', prompt]

    try:
        result = subprocess.run([target] + args, capture_output=True, text=True, timeout=120, check=False)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    if result.returncode != 0:
        return None
    output = (result.stdout or '').strip()
    return output or None