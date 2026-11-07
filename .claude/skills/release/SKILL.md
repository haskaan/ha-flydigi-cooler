---
name: release
description: Prepare and publish a new version of the Flydigi Cooler integration (version bump, checks, tag, push).
disable-model-invocation: true
argument-hint: "[patch|minor|major|X.Y.Z]"
---

# Release a new version

Requested version: `$ARGUMENTS` (if empty, propose one and ask).

## 1. Preconditions
- Working tree is clean and on `main`: `git status --short`, `git branch --show-current`.
- Local `main` is up to date: `git fetch && git status -sb`.
- Stop and report if any of these fail.

## 2. Pick the version
- Last tag: `git describe --tags --abbrev=0`. Changes since: `git log <last-tag>..HEAD --oneline`.
- Semver: `patch` = fixes only, `minor` = new features/options, `major` = breaking changes
  (renamed entities, unique_ids, select options or services; raised minimum HA version).
- If no version was given, propose one with a one-line reason and wait for confirmation.

## 3. Checks
- Tests: `pytest -q`. All must pass.
- `strings.json` and `translations/en.json` are identical, `translations/tr.json` has the same keys:

  ```bash
  python -c "import json;l=lambda p:json.load(open(p,encoding='utf-8'));k=lambda d,p='':{p+a for a,v in d.items() for a in ([a] if not isinstance(v,dict) else [a+'.'+x for x in k(v)])};s,e,t=[l('custom_components/flydigi_cooler/'+f) for f in ('strings.json','translations/en.json','translations/tr.json')];print('en==strings:',s==e);print('tr missing:',sorted(k(s)-k(t)));print('tr extra:',sorted(k(t)-k(s)))"
  ```
- `README.md` and `README.tr.md` both describe any new feature or breaking change.
- No personal data in the diff since the last tag (IPs, MAC addresses, webhook IDs, tokens).

## 4. Bump, commit, tag
- Set `"version"` in `custom_components/flydigi_cooler/manifest.json`.
- Update the "current" version in `AGENTS.md`.
- Commit: `Release vX.Y.Z`.
- Annotated tag: `git tag -a vX.Y.Z -m "vX.Y.Z - <short summary>"`.

## 5. Push (ask first)
- Show the commit and tag, then **ask the user** before pushing.
- `git push origin main` and `git push origin vX.Y.Z`.
- Tell the user to create a GitHub release from the tag (HACS shows release notes from it),
  and offer a draft of the notes from the commit list.
