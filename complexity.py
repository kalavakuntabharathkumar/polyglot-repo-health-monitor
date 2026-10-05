import os
from pathlib import Path
from tree_sitter import Language, Parser

EXT_TO_LANGUAGE = {
    '.py': 'python',
    '.java': 'java',
    '.js': 'javascript',
    '.jsx': 'javascript',
    '.mjs': 'javascript',
    '.cjs': 'javascript',
    '.cs': 'csharp',
}
IGNORED_DIRS = {'.git', 'node_modules', 'venv', '__pycache__', 'build', 'dist', 'target', '.idea'}
_BRANCH = {
    'if_statement', 'for_statement', 'for_in_statement', 'foreach_statement',
    'while_statement', 'do_statement', 'try_statement', 'catch_clause',
    'switch_statement', 'switch_expression', 'conditional_expression',
    'except_clause', 'with_statement', 'and_expression', 'or_expression',
    'if_expression', 'match_statement',
}
_FUNCTIONS = {'function_definition', 'method_declaration', 'constructor_declaration',
              'function_declaration', 'function', 'arrow_function'}
_BLOCKS = _FUNCTIONS | {
    'if_statement', 'for_statement', 'for_in_statement', 'foreach_statement',
    'while_statement', 'do_statement', 'try_statement', 'catch_clause',
    'switch_statement', 'with_statement', 'class_declaration',
    'interface_declaration', 'lambda',
}
_languages = {}


def language_for_path(path):
    return EXT_TO_LANGUAGE.get(Path(path).suffix.lower())


def _load_language(language):
    if language in _languages:
        return _languages[language]
    module_name = {'python': 'tree_sitter_python', 'java': 'tree_sitter_java',
                   'javascript': 'tree_sitter_javascript',
                   'csharp': 'tree_sitter_c_sharp'}.get(language)
    if not module_name:
        return None
    module = __import__(module_name)
    language_object = Language(module.language())
    _languages[language] = language_object
    return language_object


def _node_text(node):
    return node.text.decode('utf-8', errors='ignore').strip()


def _count_branches(node):
    total = 0
    stack = [node]
    while stack:
        current = stack.pop()
        if current.type in _BRANCH:
            total += 1
        stack.extend(current.children)
    return total


def _max_depth(node):
    maximum = 0
    stack = [(node, 0)]
    while stack:
        current, depth = stack.pop()
        if current.type in _BLOCKS:
            depth += 1
        maximum = max(maximum, depth)
        stack.extend((child, depth) for child in current.children)
    return maximum


def _function_name(node):
    name = node.child_by_field_name('name')
    if name:
        return _node_text(name)
    for child in node.children:
        if child.type == 'name':
            return _node_text(child)
    return None


def _extract_functions(root):
    functions = []
    stack = [root]
    while stack:
        node = stack.pop()
        if node.type in _FUNCTIONS:
            functions.append({
                'name': _function_name(node) or f'anonymous_{node.start_byte}',
                'start_line': node.start_line + 1,
                'lines': node.end_line - node.start_line + 1,
                'complexity': 1 + _count_branches(node),
                'nesting_depth': _max_depth(node),
            })
        stack.extend(node.children)
    return functions


def analyze_source(path, source, language):
    grammar = _load_language(language)
    if grammar is None:
        return None
    parser = Parser(grammar)
    tree = parser.parse(source.encode('utf-8'))
    root = tree.root_node
    functions = _extract_functions(root)
    return {
        'path': path,
        'language': language,
        'lines': source.count('\n') + 1,
        'function_count': len(functions),
        'complexity_sum': sum(item['complexity'] for item in functions),
        'functions': functions,
    }


def iter_code_files(root, max_files=200):
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in IGNORED_DIRS]
        relative_dir = os.path.relpath(dirpath, root)
        for filename in filenames:
            relative = filename if relative_dir == '.' else os.path.join(relative_dir, filename)
            if language_for_path(relative):
                found.append(Path(relative).as_posix())
                if len(found) >= max_files:
                    return found
    return found


def _analyze_items(items, repo, commit_sha):
    data = {'repo': repo, 'commit_sha': commit_sha, 'language_breakdown': {}, 'files': []}
    for relative_path, source in items:
        language = language_for_path(relative_path)
        if not language:
            continue
        metrics = analyze_source(relative_path, source, language)
        if not metrics:
            continue
        data['files'].append(metrics)
        data['language_breakdown'][language] = data['language_breakdown'].get(language, 0) + metrics['lines']
    all_functions = []
    for file_metrics in data.get('files', []):
        for function in file_metrics.get('functions', []):
            all_functions.append({**function, 'path': file_metrics['path']})
    total = len(all_functions)
    data['summary'] = {
        'total_functions': total,
        'avg_complexity': round(sum(item['complexity'] for item in all_functions) / total, 2) if total else 0,
        'max_complexity': max((item['complexity'] for item in all_functions), default=0),
        'avg_nesting': round(sum(item['nesting_depth'] for item in all_functions) / total, 2) if total else 0,
        'high_complexity': sum(1 for item in all_functions if item['complexity'] >= 15),
        'high_nesting': sum(1 for item in all_functions if item['nesting_depth'] >= 5),
    }
    data['top_functions'] = sorted(
        all_functions,
        key=lambda item: (-item['complexity'], -item['nesting_depth'], item['path'], item['start_line'])
    )[:50]
    return data


def analyze_directory(root, commit_sha, max_files=200):
    def items():
        for relative_path in iter_code_files(root, max_files):
            try:
                source = Path(root, relative_path).read_text(encoding='utf-8', errors='ignore')
            except OSError:
                continue
            yield relative_path, source

    return _analyze_items(items(), Path(root).name, commit_sha)


def analyze_sources(sources, commit_sha, max_files=200):
    return _analyze_items(sources[:max_files], 'pull-request', commit_sha)