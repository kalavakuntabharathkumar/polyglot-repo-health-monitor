import requests
from urllib.parse import quote


BASE_URL = 'https://api.github.com'
TIMEOUT = 30


class GithubError(Exception):
    pass


class GithubClient:
    def __init__(self, token=None):
        self.session = requests.Session()
        self.session.headers['Accept'] = 'application/vnd.github.v3+json'
        if token:
            self.session.headers['Authorization'] = f'Bearer {token}'

    def _get(self, url, **kwargs):
        try:
            response = self.session.request('GET', url, timeout=TIMEOUT, **kwargs)
        except requests.RequestException as exc:
            raise GithubError(f'Network error calling GitHub API: {exc}') from exc
        if response.status_code >= 400:
            raise GithubError(f'GitHub API returned {response.status_code}: {response.text[:300]}')
        try:
            return response.json()
        except ValueError as exc:
            raise GithubError('GitHub API returned a non-JSON response') from exc

    def _raw(self, url, **kwargs):
        headers = dict(self.session.headers)
        headers['Accept'] = 'application/vnd.github.v3.raw'
        try:
            response = self.session.request('GET', url, headers=headers, timeout=TIMEOUT, **kwargs)
        except requests.RequestException as exc:
            raise GithubError(f'Network error calling GitHub API: {exc}') from exc
        if response.status_code >= 400:
            raise GithubError(f'GitHub API raw fetch returned {response.status_code}')
        return response.text

    def get_repo(self, owner, repo):
        return self._get(f'{BASE_URL}/repos/{owner}/{repo}')

    def get_latest_commit(self, owner, repo):
        repo_info = self.get_repo(owner, repo)
        data = self._get(f'{BASE_URL}/repos/{owner}/{repo}/commits',
                         params={'sha': repo_info.get('default_branch', 'main'), 'per_page': 1})
        if not data:
            raise GithubError('GitHub API returned no commits')
        return data[0]['sha']

    def get_languages(self, owner, repo):
        return self._get(f'{BASE_URL}/repos/{owner}/{repo}/languages')

    def get_pr(self, owner, repo, number):
        return self._get(f'{BASE_URL}/repos/{owner}/{repo}/pulls/{number}')

    def get_pr_files(self, owner, repo, number):
        return self._get(f'{BASE_URL}/repos/{owner}/{repo}/pulls/{number}/files',
                         params={'per_page': 100})

    def get_raw_file(self, owner, repo, path, ref):
        url = f'{BASE_URL}/repos/{owner}/{repo}/contents/{quote(path)}'
        return self._raw(url, params={'ref': ref})