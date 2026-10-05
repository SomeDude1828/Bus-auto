# Bus-auto

Small PWA for the school commute from Polje to Vegova.

## Settings
- Arrival default: 07:00
- Lines: 27 -> Konzorcij; 11 -> Drama; 25 -> Bavarski dvor
- Home -> Polje: 8 min
- Wake: 20 min before bus
- Leave home: 8 min before bus
- Backup alarm: 15 min before wake

## GitHub Pages
Upload all files to the repository root, then Settings -> Pages -> Deploy from a branch -> `main` / `/ (root)`.
Open the Pages URL in Chrome on Android and choose Add to home screen / Install app.

The app uses LPP's public GTFS feed: https://data.lpp.si/api/gtfs/feed.zip
It uses scheduled data only; check live conditions in the morning as intended.
