# GitHub build guide

The workflow in `.github/workflows/windows-installer.yml` builds a standalone Windows executable with PyInstaller and packages it with Inno Setup.

1. Open the repository's **Actions** tab and enable Actions if prompted.
2. Select **Build Claude Muslim Windows Installer**.
3. Click **Run workflow** on the `main` branch.
4. When complete, open the run and download the `ClaudeMuslim-Windows-Installer` artifact.
5. Extract the artifact ZIP to get `ClaudeMuslim-Setup.exe`.

For a GitHub Release, create a tag named like `v1.0.0` and push it. The workflow builds the installer and attaches it to that release.

The installer is per-user and does not require administrator privileges. Windows SmartScreen may warn because the executable is unsigned.
