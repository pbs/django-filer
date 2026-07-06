# PBS Fork – Developer Guide

## Versioning Scheme

This fork uses a PBS-specific versioning scheme:

```
<upstream_version>+pbs.<pbs_number>
```

Example: `3.4.4+pbs.1`, `3.4.4+pbs.2`

Development (pre-release) versions append a dev suffix:

```
<upstream_version>+pbs.<pbs_number>.dev.g<commit_sha>.YYYYMMDD
```

Example: `3.4.4+pbs.1.dev.g1a2b3c4d.20260617`

The version is stored in `filer/__init__.py` and read dynamically by `pyproject.toml`.

---

## Makefile Targets

Run `make help` to see all available targets. Summary:

| Target | Description |
|--------|-------------|
| `make help` | Show all available targets |
| `make test-build` | Build the test Docker image |
| `make test` | Run unit tests in a Docker container (builds image if missing) |
| `make test-verbose` | Run tests with verbose output, stop on first failure |
| `make test-shell` | Open a shell in the test container (for debugging) |
| `make test-clean` | Remove the test Docker image |
| `make bump-pbs` | Bump the PBS version number (e.g. `+pbs.1` → `+pbs.2`) |
| `make bump-prekind` | Create a dev pre-release version from the current commit |
| `make build` | Build sdist and wheel packages into `dist/` |
| `make publish-nexus` | Build and upload packages to Nexus |
| `make publish-nexus-dry-run` | Build and validate packages without uploading |

---

## How to Publish a New Version

### Prerequisites

- Python 3 installed
- `bump-my-version` installed (`pip install bump-my-version`)
- `~/.pypirc` configured with a `[nexus]` section containing your repository URL and credentials

### Steps

#### 1. Run tests

```bash
make test
```

Ensure all tests pass before proceeding.

#### 2. Bump the PBS version

```bash
make bump-pbs
```

This increments the PBS number (e.g. `3.4.4+pbs.1` → `3.4.4+pbs.2`) in both `filer/__init__.py` and `.bumpversion.toml`.

#### 3. Commit and push

```bash
git add filer/__init__.py .bumpversion.toml
git commit -m "Bump to $(grep __version__ filer/__init__.py | sed "s/.*'//;s/'.*//")"
git push
```

#### 4. Publish to Nexus

```bash
make publish-nexus
```

This will:
1. Clean previous build artifacts
2. Build source distribution and wheel (`python3 -m build`)
3. Upload to Nexus using `twine` with the `[nexus]` section from `~/.pypirc`

#### 5. (Optional) Validate without uploading

```bash
make publish-nexus-dry-run
```

Runs `twine check` on the built packages to verify they are well-formed.

---

## Publishing a Dev (Pre-release) Version

Use this when you need to test unreleased changes without a formal PBS bump:

```bash
make bump-prekind
```

This creates a version like `3.4.4+pbs.1.dev.g1a2b3c4d.20260617` based on the current HEAD commit and date.

You can override the commit SHA:

```bash
make bump-prekind sha=abc12345
```

Then publish normally:

```bash
make publish-nexus
```

> **Note:** To bump again on the same commit, you must first run `make bump-pbs` to move to the next PBS number.

---

## Publishing via GitHub Actions (Bento3)

You can also publish a new version using the **bento3** GitHub Actions workflow:

🔗 [publish_django_filer.yml](https://github.com/pbs-digital/bento3/actions/workflows/publish_django_filer.yml)

Trigger the workflow manually from the Actions tab. This is the recommended approach for CI-driven releases.

---

## `~/.pypirc` Configuration (for local publishing)

Ensure your `~/.pypirc` contains a `[nexus]` entry:

```ini
[distutils]
index-servers =
    nexus

[nexus]
repository = https://your-nexus-instance/repository/pypi-hosted/
username = your-username
password = your-password-or-token
```

