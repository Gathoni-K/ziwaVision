# ZiwaVision — Environment Setup Guide

This guide gets a fresh machine from nothing to a working local development
environment for ZiwaVision. It assumes no prior pyenv, Python, or acmadDL
setup. Follow it top to bottom on a new machine; on an existing machine
already set up, skip to [Per-Project Setup](#per-project-setup).

Written for Arch Linux. Notes for other distros are called out where the
steps diverge.

---

## Why this setup looks the way it does

ZiwaVision depends on `acmadDL`, which requires **Python 3.12 or newer**.
Most systems, especially freshly installed ones, ship whatever the current
newest Python release is — at time of writing this can be 3.14 or later.
Newer Python releases regularly run ahead of the scientific Python
ecosystem's own dependency wheels (xarray, netCDF4, the CDS API stack, and
others that acmadDL depends on), so installing acmadDL against the system's
newest Python often fails or behaves unpredictably.

The fix is not to change the system's default Python. It's to install a
**second, specific Python version (3.12.7) alongside it**, using `pyenv`,
and to point each project's virtual environment at that version explicitly.
This keeps the system Python untouched and gives every acmadDL-dependent
project a known-working interpreter.

---

## Global Setup

**Do this once per machine. Never repeat these steps once done — if you're
setting up a new project on a machine that's already been through this
section, skip straight to [Per-Project Setup](#per-project-setup).**

### 1. Install pyenv

```bash
sudo pacman -S pyenv
```

*(Debian/Ubuntu: use the [pyenv-installer](https://github.com/pyenv/pyenv#automatic-installer) script instead, since it isn't in the default apt repos.)*

### 2. Wire pyenv into your shell config

This step is what makes `python` on your command line resolve to pyenv's
managed versions instead of always falling back to the system Python. It
must go in the config file for **the shell you actually use** — check with
`echo $SHELL` first. For zsh, that's `~/.zshrc`; for bash, `~/.bashrc`.

```bash
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.zshrc
echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.zshrc
echo 'eval "$(pyenv init -)"' >> ~/.zshrc
```

Reload the config so the current terminal session picks it up:

```bash
source ~/.zshrc
```

**Verify it took effect before moving on:**

```bash
grep -n pyenv ~/.zshrc
```

You should see the three lines you just added, each with a line number. If
nothing prints, the lines didn't land — re-run the `echo` commands and
check you're editing the file your shell actually reads (`echo $SHELL`
again if unsure).

### 3. Install Python 3.12.7 via pyenv

```bash
pyenv install 3.12.7
```

This compiles Python from source and can take a few minutes. You may see a
warning partway through about `tkinter` / `_tkinter` failing to build —
this is harmless and safe to ignore for this project, since nothing here
depends on tkinter. The install has succeeded as long as the final line
reads:

```
Installed Python-3.12.7 to /home/<you>/.pyenv/versions/3.12.7
```

*(If you do need tkinter later for something else: `sudo pacman -S tk`,
then `pyenv uninstall 3.12.7` and re-run the install.)*

### 4. Confirm the global setup end to end

```bash
which python
```

Expected output: `/home/<you>/.pyenv/shims/python`

If this instead shows `/usr/bin/python` (or another system path), the shell
config from step 2 isn't active. Re-check step 2 before continuing —
nothing downstream will work correctly until `which python` resolves to
the pyenv shim.

```bash
pyenv versions
```

Should list `3.12.7` as an available version.

**Global setup is now complete and permanent.** You will not repeat any of
the above on this machine again, for this or any future acmadDL project.

---

## Per-Project Setup

**Repeat this section for every new project that depends on acmadDL** —
whether that's ZiwaVision itself on a new machine, or a future unrelated
project with the same dependency.

### 1. Create and enter the project folder

```bash
mkdir -p ~/Projects/ZiwaVision
cd ~/Projects/ZiwaVision
```

(Adjust the path to wherever you keep your projects — the exact location
doesn't matter, only that you're inside it for the remaining steps.)

### 2. Pin this folder to Python 3.12.7

```bash
pyenv local 3.12.7
```

This writes a `.python-version` file into the current folder. From this
point on, any time you `cd` into this folder (or a subfolder of it), pyenv
automatically switches `python` to 3.12.7 — no manual switching required.

### 3. Confirm the pin took effect

```bash
python --version
```

Expected output: `Python 3.12.7`

If this shows a different version, the shim isn't picking up the local
pin correctly — re-check that Global Setup step 4 passed on this machine
before continuing.

### 4. Create the virtual environment

```bash
python -m venv venv
```

Because `python` is already correctly resolved to 3.12.7 at this point
(steps 2–3), the venv is built from the right interpreter automatically.

### 5. Activate the virtual environment

```bash
source venv/bin/activate
```

Your terminal prompt should now show `(venv)` at the start. This confirms
you're working inside the isolated environment, not system Python.

**This is the one step you repeat every time you sit down to work on the
project in a new terminal session** — see
[Everyday Use](#everyday-use-after-setup) below.

### 6. Re-confirm the Python version inside the venv

```bash
python --version
```

Expected output: `Python 3.12.7` — confirms the venv itself was built
correctly, not just that pyenv was resolving correctly outside it.

### 7. Install project dependencies

```bash
pip install acmadDL
```

Add any other packages the specific project needs. For ZiwaVision itself,
that's:

```bash
pip install opencv-python
pip install africas2s
```

After installing OpenCV, confirm the version is 5.x, since the OpenCV AI
Competition specifically requires OpenCV 5:

```bash
python -c "import cv2; print(cv2.__version__)"
```

### 8. (acmadDL-specific) Set up Copernicus CDS credentials

Most acmadDL products need Climate Data Store credentials. Create a file
at `~/.cdsapirc`:

```bash
cat > ~/.cdsapirc << 'EOF'
url: https://cds.climate.copernicus.eu/api
key: <YOUR-CDS-API-KEY>
EOF
```

Get the API key from your account at https://cds.climate.copernicus.eu.
You also need to accept each dataset's terms of use in the CDS web UI
before first download — a missed acceptance shows up as a `403` error
naming exactly which dataset's license is still unaccepted.

*(This step is machine-and-account-level, not strictly per-project, but is
listed here since it's easy to forget until acmadDL's first real fetch
fails on a fresh machine.)*

---

## Everyday Use (after setup)

Once a project has been through Per-Project Setup once, coming back to
work on it in a new terminal session takes exactly one command:

```bash
cd ~/Projects/ZiwaVision
source venv/bin/activate
```

Everything else — the pyenv version pin, the installed packages, the venv
itself — persists on disk and does not need to be recreated.

When finished working:

```bash
deactivate
```

(Not required, but tidy if the same terminal will next be used for
something unrelated.)

---

## Troubleshooting Reference

| Symptom | Cause | Fix |
|---|---|---|
| `which python` shows `/usr/bin/python` instead of the pyenv shim | Shell config from Global Setup step 2 isn't active | Confirm the three lines are in the correct shell config file (`echo $SHELL` to check which one), then `source` it |
| `.python-version` shows `3.12.7` but `python --version` still shows the system version | Same as above — `.python-version` only works if pyenv's shims are already ahead of system Python on `PATH` | Same fix as above |
| Warning about `_tkinter` / `ModuleNotFoundError: No module named '_tkinter'` during `pyenv install` | Tk development headers not present on the system at build time | Harmless for this project — ignore. Fix only if tkinter is actually needed later (`sudo pacman -S tk`, reinstall the Python version) |
| `pip install acmadDL` fails or tries to compile packages from source | Installing against a Python version too new for the current scientific-stack wheels | Confirm you're inside a venv built from pyenv's 3.12.7, not system Python (`python --version` inside the active venv) |
| `403` error when acmadDL tries to fetch CDS data | A dataset's terms of use haven't been accepted in the CDS web UI | The error names the specific dataset — accept its license on the CDS site, then retry |

---

## Quick Reference — Full Command Sequence

For copy-paste convenience once you understand what each step does.

**Global (once per machine):**
```bash
sudo pacman -S pyenv
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.zshrc
echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.zshrc
echo 'eval "$(pyenv init -)"' >> ~/.zshrc
source ~/.zshrc
pyenv install 3.12.7
```

**Per project (once per project):**
```bash
mkdir -p ~/Projects/<project-name>
cd ~/Projects/<project-name>
pyenv local 3.12.7
python -m venv venv
source venv/bin/activate
pip install acmadDL
```

**Every work session (every time):**
```bash
cd ~/Projects/<project-name>
source venv/bin/activate
```