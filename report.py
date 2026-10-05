def format_percentages(languages):
    total = sum(languages.values())
    if not total:
        return 'none detected'
    return ', '.join(f'{name} {value / total:.1%}' for name, value in sorted(languages.items(), key=lambda item: -item[1]))


def table(headers, rows):
    lines = ['| ' + ' | '.join(headers) + ' |', '|' + '|'.join([' --- '] * len(headers)) + '|']
    for row in rows:
        lines.append('| ' + ' | '.join(str(value) for value in row) + ' |')
    return lines


def render_markdown(data, copilot_text, pr_number=None):
    info = data.get('repo_info', {})
    summary = data.get('summary', {})
    lines = ['# Repository Health Report', '']
    lines.append('- Repository: ' + str(info.get('full_name', data.get('repo'))))
    lines.append('- Commit: `' + str(data.get('commit_sha', 'unknown')) + '`')
    if pr_number:
        lines.append('- Pull request: #' + str(pr_number))
    if info:
        lines.append('- Open issues: ' + str(info.get('open_issues_count', 'unknown')))
        lines.append('- Default branch: ' + str(info.get('default_branch', 'unknown')))
    lines.append('- GitHub language breakdown: ' + format_percentages(data.get('api_languages') or {}))
    lines.append('- Analyzed language breakdown: ' + format_percentages(data.get('language_breakdown') or {}))
    lines.append('')
    lines.append('## Summary')
    lines.append('')
    for key, label in [('total_functions', 'Total functions'), ('avg_complexity', 'Average cyclomatic complexity'),
                       ('max_complexity', 'Maximum cyclomatic complexity'), ('avg_nesting', 'Average nesting depth'),
                       ('high_complexity', 'Functions with complexity >= 15'), ('high_nesting', 'Functions with nesting >= 5')]:
        lines.append('- ' + label + ': ' + str(summary.get(key, 0)))
    lines.append('')
    lines.append('## Top files')
    lines.extend(table(['Path', 'Language', 'Lines', 'Functions', 'Complexity sum'],
                       [(item['path'], item['language'], item['lines'], item['function_count'], item['complexity_sum'])
                        for item in sorted(data.get('files', []), key=lambda item: -item['complexity_sum'])[:10]]))
    lines.append('')
    lines.append('## Top functions')
    lines.extend(table(['Path', 'Function', 'Start line', 'Complexity', 'Nesting depth'],
                       [(item['path'], item['name'], item['start_line'], item['complexity'], item['nesting_depth'])
                        for item in data.get('top_functions', [])[:25]]))
    lines.append('')
    lines.append('## Refactor suggestions')
    lines.append('')
    if copilot_text:
        lines.append(copilot_text.strip())
    else:
        lines.append('Copilot CLI was unavailable or returned no output. Install a Copilot CLI and set COPILOT_CLI_BIN if needed.')
    lines.append('')
    return '\n'.join(lines)