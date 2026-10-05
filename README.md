# School Bus

Tiny PWA for planning the next school morning from **Polje**.

- 27 → Konzorcij (preferred)
- 11 → Drama
- 25 → Bavarski dvor
- Home → Polje: 8 min
- Wake: 20 min before the bus
- Backup alarm: 15 min before wake
- Default target: 07:00

## GitHub Pages setup

1. Put these files in the root of the `main` branch.
2. Settings → Pages → Deploy from a branch → `main` → `/ (root)`.
3. Settings → Actions → General → Workflow permissions: **Read and write permissions**.
4. Run **Actions → Update LPP timetable → Run workflow** once manually. The workflow also runs daily at 17:00 UTC.
5. Open the Pages URL on Android and use Chrome → Add to home screen / Install app.

The browser does **not** download the LPP GTFS feed directly. GitHub Actions downloads the official scheduled feed and creates `data.json`, which avoids browser CORS problems.

This uses scheduled timetable data, not live delays/cancellations. Check LPP/Google Maps again in the morning.
