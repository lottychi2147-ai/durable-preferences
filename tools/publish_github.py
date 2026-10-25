#!/usr/bin/env python3
"""Publish a manifest-verified package using the user's own authenticated gh CLI.
Default is a local dry run. No tokens are read, printed, or stored by this script.
No force push, remote deletion, or automatic private-to-public conversion.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DESCRIPTION = 'Long-term preference memory Skill for AI agents: sparse learning, scoped state, visual-memory research.'
TOPICS = ['ai-memory', 'agent-skills', 'long-term-memory', 'preference-learning', 'visual-memory', 'sqlite', 'python']
ISSUE_TITLE = 'RFC-0001｜邀請共研：AI 圖像記憶的編碼、累積與讀取'


class PublishError(RuntimeError):
    pass


def validate_repo(value: str) -> tuple[str, str]:
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9][A-Za-z0-9._-]{0,99}', value):
        raise PublishError('Use an explicit GitHub owner/repository name.')
    return tuple(value.split('/', 1))


def safe_path(root: Path, relative: str) -> Path:
    p = PurePosixPath(relative)
    if p.is_absolute() or not p.parts or any(x in ('..', '.git', '') for x in p.parts) or '\\' in relative:
        raise PublishError(f'Unsafe manifest path: {relative}')
    current = root
    for part in p.parts:
        current = current / part
        if current.is_symlink():
            raise PublishError(f'Symlink is not allowed in the publication: {relative}')
    if root.resolve() not in current.resolve().parents:
        raise PublishError(f'Path escapes package: {relative}')
    return current


def verify_package(root: Path) -> list[str]:
    manifest = json.loads((root / 'MANIFEST.json').read_text(encoding='utf-8'))
    entries = manifest.get('files', {})
    if not entries or 'scripts/memory_core.py' not in entries or 'README.md' not in entries:
        raise PublishError('Incomplete publication manifest.')
    for name, expected in entries.items():
        path = safe_path(root, name)
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise PublishError(f'Checksum mismatch: {name}')
        if path.suffix in ('.sqlite', '.sqlite3', '.db', '.pem', '.key') or path.name.startswith('.env'):
            raise PublishError(f'Private/runtime file is not publishable: {name}')
    return sorted(entries) + ['MANIFEST.json']


def run(cmd: list[str], *, cwd: Path | None = None, check: bool = True, timeout: int = 180) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env.update({'GH_PROMPT_DISABLED': '1', 'GIT_TERMINAL_PROMPT': '0', 'PYTHONIOENCODING': 'utf-8'})
    result = subprocess.run(cmd, cwd=cwd, env=env, text=True, encoding='utf-8', errors='replace', capture_output=True, timeout=timeout)
    if check and result.returncode:
        raise PublishError(f'{cmd[0]} {cmd[1]} failed:\n{result.stderr.strip() or result.stdout.strip()}')
    return result


def git(*args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    # Only this subprocess uses the gh credential helper; do not rewrite global git configuration.
    return run(['git', '-c', 'credential.helper=', '-c', 'credential.https://github.com.helper=!gh auth git-credential', *args], cwd=cwd, check=check)


def copy_selected(root: Path, checkout: Path, names: list[str]) -> None:
    for name in names:
        source, target = safe_path(root, name), safe_path(checkout, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        if name == '.gitignore' and target.exists():
            old = target.read_text(encoding='utf-8')
            extra = [line for line in source.read_text(encoding='utf-8').splitlines() if line and line not in old.splitlines()]
            target.write_text(old.rstrip() + '\n' + '\n'.join(extra) + '\n', encoding='utf-8')
        else:
            shutil.copy2(source, target)
    # Existing repository .gitignore rules may be preserved, so update this one manifest entry.
    manifest_path = checkout / 'MANIFEST.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    manifest['files']['.gitignore'] = hashlib.sha256((checkout / '.gitignore').read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True, help='Explicit owner/name; no default account.')
    parser.add_argument('--apply', action='store_true', help='Actually create/push the public repository.')
    parser.add_argument('--update-existing', action='store_true', help='Allow updating an existing public durable-preferences repository.')
    args = parser.parse_args(argv)
    try:
        owner, name = validate_repo(args.repo)
        if name != 'durable-preferences':
            raise PublishError('Keep the repository/folder name durable-preferences to match the Skill validator.')
        names = verify_package(ROOT)
        plan = {'mode': 'apply' if args.apply else 'dry-run', 'repository': args.repo,
                'new_repository_visibility': 'public', 'private_repository_visibility_change': 'refused',
                'files': len(names), 'core_version': '0.2.0', 'license': 'MIT; see LICENSE',
                'community': 'Enable Issues/Discussions and create an idempotent RFC issue.',
                'history': 'No force push; preserve unrelated files. Protected branch failure stops the script.'}
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        if not args.apply:
            print('Local preview only. No network request or GitHub change performed.')
            return 0
        missing = [exe for exe in ('git', 'gh') if not shutil.which(exe)]
        if missing:
            raise PublishError('Missing prerequisites: ' + ', '.join(missing) + '. Use a terminal with Git and GitHub CLI; sign in with gh auth login first.')
        run(['gh', 'auth', 'status', '--hostname', 'github.com'])
        profile = json.loads(run(['gh', 'api', 'user']).stdout)
        if profile['login'].casefold() != owner.casefold():
            raise PublishError('Authenticated account does not match the explicit repository owner. No changes made.')
        # Test before any remote mutation. Outputs remain in a temporary private directory.
        with tempfile.TemporaryDirectory(prefix='durable-preferences-preflight-') as checkdir:
            run([sys.executable, 'tests/run_all.py', '--unit-only', '--output', str(Path(checkdir)/'unit')], cwd=ROOT)
            run([sys.executable, 'tests/acceptance_v020.py', '--root', '.', '--out', str(Path(checkdir)/'acceptance.json')], cwd=ROOT)
            evidence = json.loads((Path(checkdir)/'acceptance.json').read_text(encoding='utf-8'))
            if evidence['passed'] != evidence['total']:
                raise PublishError('Learning acceptance failed. No remote changes made.')
        lookup = run(['gh', 'api', f'repos/{args.repo}'], check=False)
        exists = lookup.returncode == 0
        if not exists and 'HTTP 404' not in lookup.stderr:
            raise PublishError('Cannot determine repository status; refusing to create or change anything.\n' + lookup.stderr)
        if exists:
            metadata = json.loads(lookup.stdout)
            if metadata.get('private'):
                raise PublishError('Existing repository is private. Refusing to expose its historical contents; review it separately or publish a clean repository.')
            if not args.update_existing:
                raise PublishError('Repository exists. Review it, then rerun with --update-existing to update only manifest-listed paths.')
        else:
            run(['gh', 'repo', 'create', args.repo, '--public', '--description', DESCRIPTION])
        work = Path(tempfile.mkdtemp(prefix='durable-preferences-publish-'))
        checkout = work/'durable-preferences'
        print('Isolated publication checkout:', str(checkout))
        try:
            git('clone', f'https://github.com/{args.repo}.git', str(checkout))
            has_commit = git('rev-parse', '--verify', 'HEAD', cwd=checkout, check=False).returncode == 0
            if has_commit:
                skill = checkout/'SKILL.md'
                if not skill.exists() or not re.search(r'^name:\s*durable-preferences\s*$', skill.read_text(encoding='utf-8'), re.M):
                    raise PublishError('Existing repository is not identifiable as this Skill; refusing to overwrite it.')
                existing_licenses = [checkout/x for x in ('LICENSE', 'LICENSE.md', 'LICENSE.txt', 'COPYING') if (checkout/x).exists()]
                if existing_licenses and (len(existing_licenses) != 1 or existing_licenses[0].name != 'LICENSE' or existing_licenses[0].read_bytes() != (ROOT/'LICENSE').read_bytes()):
                    raise PublishError('Existing repository license differs from this MIT package; reconcile it before updating.')
            else:
                git('checkout', '-B', 'main', cwd=checkout)
            copy_selected(ROOT, checkout, names)
            verify_package(checkout)
            # Batch only allowlisted paths; never stage unrelated user content.
            for i in range(0, len(names), 40):
                git('add', '--', *names[i:i+40], cwd=checkout)
            diff = git('diff', '--cached', '--quiet', cwd=checkout, check=False)
            if diff.returncode not in (0, 1):
                raise PublishError('Could not inspect staged changes.')
            if diff.returncode == 1:
                email = f"{profile['id']}+{profile['login']}@users.noreply.github.com"
                git('-c', 'user.name=紀順文', '-c', f'user.email={email}', 'commit', '-m', 'Publish durable-preferences v0.2.0 with method, validation and visual-memory RFC', cwd=checkout)
            branch = git('symbolic-ref', '--short', 'HEAD', cwd=checkout).stdout.strip()
            git('push', '--set-upstream', 'origin', branch, cwd=checkout)
            for path in ('README.md', 'SKILL.md', 'scripts/memory_core.py'):
                remote_sha = run(['gh', 'api', f'repos/{args.repo}/contents/{path}', '-f', f'ref={branch}', '-X', 'GET', '--jq', '.sha']).stdout.strip()
                expected = git('hash-object', path, cwd=checkout).stdout.strip()
                if remote_sha != expected:
                    raise PublishError(f'Post-push remote verification failed: {path}')
            settings = ['gh', 'repo', 'edit', args.repo, '--description', DESCRIPTION, '--enable-issues', '--enable-discussions']
            for topic in TOPICS: settings += ['--add-topic', topic]
            run(settings)
            existing_issues = json.loads(run(['gh', 'issue', 'list', '--repo', args.repo, '--state', 'all', '--search', 'RFC-0001 in:title', '--limit', '100', '--json', 'title,url']).stdout)
            issue_url = next((x['url'] for x in existing_issues if x['title'] == ISSUE_TITLE), None)
            if issue_url is None:
                issue_url = run(['gh', 'issue', 'create', '--repo', args.repo, '--title', ISSUE_TITLE, '--body-file', str(checkout/'docs/RFC-0001-image-memory.md')]).stdout.strip()
            final = json.loads(run(['gh', 'repo', 'view', args.repo, '--json', 'url,isPrivate,hasDiscussionsEnabled,hasIssuesEnabled']).stdout)
            if final['isPrivate'] or not final['hasIssuesEnabled'] or not final['hasDiscussionsEnabled']:
                raise PublishError('Files may be pushed, but public/community settings did not verify.')
            print(json.dumps({'status':'published_and_verified','repository':final,'rfc_issue':issue_url,
                              'commit':git('rev-parse','HEAD',cwd=checkout).stdout.strip()},ensure_ascii=False,indent=2))
        except Exception:
            print('Publication stopped. Partial remote changes may exist; inspect before retrying. Local checkout retained at:', str(checkout), file=sys.stderr)
            raise
        else:
            shutil.rmtree(work)
        return 0
    except (PublishError, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as e:
        print('ERROR:', str(e), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
