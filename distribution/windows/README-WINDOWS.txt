HAWK-EYE for Windows
====================

Start
-----
Double-click HAWK-EYE.exe. The application starts on 127.0.0.1 and opens in
your default browser. Use the HAWK-EYE icon in the Windows notification area
to reopen the interface, open the data directory, or stop the application.

Data
----
Cases, review history, settings, and logs live outside the installation at:

  %LOCALAPPDATA%\HAWK-EYE

Uninstalling or replacing this application folder does not remove that data.
Back up the Data folder to preserve investigations.

Model provider (optional)
-------------------------
HAWK-EYE works without an API key through deterministic fallback. To enable an
OpenAI-compatible model, create:

  %LOCALAPPDATA%\HAWK-EYE\settings.env

Use distribution/windows/settings.env.example from the source repository as the
template. Never share or commit the real key.

OCR (optional)
--------------
If this release does not contain the optional Tesseract runtime, install
Tesseract separately and set HAWKEYE_TESSERACT_PATH in settings.env.

Troubleshooting
---------------
The rotating application log is stored at:

  %LOCALAPPDATA%\HAWK-EYE\Logs\hawkeye.log

HAWK-EYE only listens on Windows loopback. Windows Firewall or router port
forwarding is not needed for this desktop distribution.
