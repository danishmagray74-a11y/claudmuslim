# Claude Muslim

A free Windows app that automatically changes your desktop wallpaper with Islamic architecture, geometric patterns and calligraphy photos, with an optional quote overlay.

- Images are sourced from Wikimedia Commons; photo credits are retained in the app.
- Wallpaper rotation is managed by Windows Task Scheduler.
- Settings and downloaded photos are stored in `%APPDATA%\ClaudeMuslim`.

## Install

Download **ClaudeMuslim-Setup.exe** from the repository's [Actions artifacts](../../actions) or [Releases](../../releases), run it, and follow the installer. The app is installed per-user and does not require administrator rights.

## Build from source

Requires Windows and Python 3.9+.

```powershell
python -m pip install pillow pyinstaller
pyinstaller --clean --noconfirm --onefile --noconsole --name ClaudeMuslim claude_muslim.py
```

## Build the installable EXE on GitHub

1. Open **Actions**.
2. Choose **Build Claude Muslim Windows Installer**.
3. Select **Run workflow**.
4. Download the `ClaudeMuslim-Windows-Installer` artifact when the run succeeds.

To publish a permanent installer, create and push a version tag such as `v1.0.0`; the workflow attaches the installer to the GitHub Release.

## Notes

- Internet access is required to fetch new photos; cached photos can be reused offline.
- Windows SmartScreen may show an unknown-publisher warning because the installer is not code-signed.
- Some built-in quotes are traditionally attributed; verify quotations before redistribution.

## License

MIT. See [LICENSE](LICENSE).
