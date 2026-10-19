---
this_file: PYPI.md
---

# Publish TypeRig to PyPI: Vassil's Windows setup

This is the one-time setup for **Vassil Kateliev**, maintaining
`kateliev/TypeRig`. Afterwards, pushing a release tag such as `v2.1.0` runs the
checks, makes a GitHub release, and publishes `typerig` to PyPI automatically.
Use **Windows PowerShell** for the commands below. No Bash or WSL is needed.

The recommended method is **PyPI Trusted Publishing**: GitHub obtains a temporary
upload credential for this workflow. You do not need to generate or share a PyPI
API token, and you do not put your PyPI password in GitHub.

## 1. Put the release files on master

Merge the packaging/release changes, including `.github/workflows/release.yml`,
into `master` before making the first tag. GitHub must have these files in the
tagged commit. The release workflow also calls `.github/workflows/check.yml`.

You need access to the `kateliev` GitHub account or suitable repository settings
permissions for the next GitHub step. Your PyPI account is separate: its username
does not have to be `kateliev`.

## 2. Prepare your PyPI account

Open [pypi.org](https://pypi.org/) and register or sign in to your own account.
Confirm its email address and complete PyPI's required two-factor authentication.
Keep the recovery codes somewhere you can find them if your authenticator is lost.
See [PyPI's account help](https://pypi.org/help/#twofa).

Check [the typerig project page](https://pypi.org/project/typerig/).
On 2026-10-19, both its project JSON and package-index endpoints returned 404,
so the **new-project path in step 4A** was appropriate. Check again when setting
this up: a missing page does not guarantee the name can be registered.
If the project exists by then, follow **4B** instead.

## 3. Create the GitHub publishing environment

1. Open [TypeRig's repository settings](https://github.com/kateliev/TypeRig/settings).
2. Select **Environments**, then **New environment**.
3. Name it exactly **`pypi`** and select **Configure environment**.
4. For the initial setup, leave deployment restrictions at their default and
   leave required reviewers unset if you want fully automatic publishing.
   Reviewer approval would make the publishing job wait for you on every release.
5. Do not add any secrets for the trusted-publishing route.
6. Under **Actions → General**, ensure Actions and the actions used by the two
   workflows are allowed. Their YAML already requests the needed job permissions:
   `contents: write` for GitHub releases, `id-token: write` for PyPI publishing.

The environment's name must match the PyPI configuration below. GitHub's
[environment guide](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments)
explains the settings and owner permissions.

## 4. Tell PyPI to trust this workflow

Use these exact values. `TypeRig` is the GitHub repository; `typerig` is the
Python distribution. The workflow filename is its file name, not its display title.

| Form field | Value |
| --- | --- |
| PyPI project name, if requested | `typerig` |
| GitHub owner | `kateliev` |
| GitHub repository | `TypeRig` |
| Workflow filename | `release.yml` |
| Environment | `pypi` |

Do not enter `.github/workflows/release.yml` in the filename field. The publishing
job is in `release.yml`, not in `check.yml`.

### 4A. If typerig does not exist on PyPI

Open [your account's Publishing page](https://pypi.org/manage/account/publishing/).
Under the GitHub publisher form, enter all five values above, then add the
**pending publisher**. Its first successful workflow upload creates the project
under your PyPI account and converts this into its regular publisher.

You do not need a preliminary manual upload. A pending publisher does not reserve
the name; if another account obtains it first, resolve project access before
publishing. PyPI documents this [new-project setup](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/).

### 4B. If typerig already exists on PyPI

In [Your projects](https://pypi.org/manage/projects/), select **Manage** next to
`typerig`, then **Publishing**. Add a GitHub publisher with the four GitHub values
above; an existing project's form does not need its PyPI name again.

If you cannot manage the project, ask its current PyPI owner to configure this
publisher or invite your PyPI account as an **Owner**, then accept the invitation.
Owning the GitHub repository does not automatically grant access to the PyPI name.
See [existing-project publishers](https://docs.pypi.org/trusted-publishers/adding-a-publisher/)
and [PyPI collaborator roles](https://pypi.org/help/#collaborator-roles).

## 5. Prepare Windows for local release commands

In PowerShell, install any tools you do not already have:

```powershell
winget install --id Git.Git -e --source winget
winget install --id GitHub.cli -e
winget install --id astral-sh.uv -e
```

Close and reopen PowerShell so it sees the updated PATH. Check the tools, install
the release scripts' Python version, and sign into GitHub:

```powershell
git --version
gh --version
uv --version
uv python install 3.11
gh auth login
gh auth setup-git
```

In GitHub login, choose GitHub.com, your `kateliev` account and browser login.
See the official [Git for Windows](https://git-scm.com/install/windows),
[GitHub CLI](https://github.com/cli/cli#installation) and
[uv installation](https://docs.astral.sh/uv/getting-started/installation/) pages
if WinGet is unavailable. uv installs the scripts' Python packages automatically.

Clone the repository, or enter your existing checkout rather than cloning again:

```powershell
git clone https://github.com/kateliev/TypeRig.git
Set-Location TypeRig
git switch master
git pull --ff-only origin master
git status --short
```

Stop if a Git command fails. Commit your intended changes first; `git status
--short` must print nothing before releasing. Use `uv run .\release.py --help`
to inspect the available options. Windows uses `uv run`, not the Unix shebang.

An annotated tag also needs Git's author identity. If this checkout does not
already have one, set it locally (use your own GitHub commit/noreply email):

```powershell
git config user.name "Vassil Kateliev"
$releaseEmail = Read-Host "Your Git commit email"
git config user.email "$releaseEmail"
```

## 6. Make the first release

First run a full preview. It tests and builds `2.1.0` in a temporary checkout,
without creating the real tag or uploading anything:

```powershell
uv run .\release.py --dry-run
if ($LASTEXITCODE -ne 0) { throw "Release preview failed; fix it before continuing." }
```

Once steps 1–4 are complete and the preview succeeds:

```powershell
uv run .\release.py
if ($LASTEXITCODE -ne 0) { throw "Release failed; see the recovery steps below." }
```

The script chooses **`v2.1.0`**, pushes that tag and the default branch atomically,
and creates the GitHub release. The tag push starts **Release and publish** in
[GitHub Actions](https://github.com/kateliev/TypeRig/actions). Wait for its checks,
release and publish jobs to turn green. A GitHub release alone does not prove
that the PyPI upload succeeded. You do not run `publish.py` locally for this route:
the temporary trusted-publishing credential is available inside Actions only.

## 7. Verify PyPI and make later releases

Open [typerig 2.1.0 on PyPI](https://pypi.org/project/typerig/2.1.0/). Its files
should include a wheel and source archive. Verify a fresh PyPI installation:

```powershell
uv run --no-project --index-url https://pypi.org/simple/ --with typerig==2.1.0 python -c "from importlib.metadata import version; from typerig.core.objects.point import Point; print(version('typerig'), Point(10, 20))"
```

This checks the Python library, not installation of the FontLab GUI scripts.
For the next release, commit your changes on `master` and run `uv run .\release.py`:
it selects `v2.1.1`. `--bump=minor` selects `v2.2.0`; `--bump=major` selects `v3.0.0`.
Rerunning at the same tagged commit resumes it instead of inventing another version.
You can also create and push your own canonical `vX.Y.Z` tag; Actions uses it as-is.

## If publishing fails

- **`invalid-publisher` / OIDC failure:** compare all fields in step 4, including
  `release.yml` and `pypi`. A pending publisher belongs under account Publishing;
  after project creation, its publisher appears under the project's Publishing.
- **Waiting for approval:** inspect the `pypi` environment's reviewer rules.
- **Project access/name error:** confirm step 4A or 4B was used correctly. A 404
  does not rule out a blocked/reserved name. Resolve that with PyPI rather than
  changing the distribution name or borrowing someone else's credentials.
- **Only the publish job failed:** fix its configuration, then choose **Re-run
  failed jobs** on the same Actions run. Or open **Release and publish → Run
  workflow**, enter `v2.1.0` as the tag, and run it from `master`.
- **Partial local GitHub release:** keep HEAD at its release commit and rerun
  `uv run .\release.py --tag=v2.1.0`. Existing assets must match; none are overwritten.
- **Already-uploaded files:** identical files are skipped. If code or an artifact
  must change, make a new commit and release a new version. Do not move a published
  tag or delete/recreate a PyPI release to replace its files.

If trusted publishing cannot be used, create your own PyPI token and add it as
the repository's **`PYPI_TOKEN`** Actions secret under **Settings → Secrets and
variables → Actions**. For an existing project, scope it to `typerig`. A first
manual project creation needs an account-wide token; prefer step 4A to avoid that.
For an exceptional local upload, enter your own token without putting it in
PowerShell history. This publishes the verified GitHub assets, then clears the
environment variable even if the command fails:

```powershell
$token = Read-Host "Your PyPI token" -AsSecureString
$env:UV_PUBLISH_TOKEN = [System.Net.NetworkCredential]::new("", $token).Password
try {
    uv run .\publish.py --tag=v2.1.0
} finally {
    Remove-Item Env:\UV_PUBLISH_TOKEN
}
```

See [RELEASING.md](RELEASING.md) for TestPyPI and recovery details.
