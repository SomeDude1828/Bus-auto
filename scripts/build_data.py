```python
import csv
import io
import json
import zipfile
import urllib.request
from datetime import date, timedelta, datetime, timezone

URL = "https://data.lpp.si/api/gtfs/feed.zip"

ROUTES = {
    "27": "Konzorcij",
    "11": "Drama",
    "25": "Bavarski dvor",
}

ORIGIN = "polje"


def read(z, name):
    with z.open(name) as f:
        return list(
            csv.DictReader(
                io.TextIOWrapper(f, "utf-8-sig", newline="")
            )
        )


def active_dates(calendar, exceptions):
    by = {}

    weekdays = [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]

    for r in calendar:
        start = date.fromisoformat(r["start_date"])
        end = date.fromisoformat(r["end_date"])

        d = start

        while d <= end:
            weekday = weekdays[d.weekday()]

            if r.get(weekday) == "1":
                by.setdefault(r["service_id"], set()).add(d.isoformat())

            d += timedelta(days=1)

    # Apply calendar exceptions.
    for e in exceptions:
        service_id = e["service_id"]
        service_dates = by.setdefault(service_id, set())

        if e["exception_type"] == "1":
            service_dates.add(e["date"])

        elif e["exception_type"] == "2":
            service_dates.discard(e["date"])

    return by


def mins(value):
    """
    Convert GTFS time into minutes after midnight.

    Supports:
      HH:MM
      HH:MM:SS

    Also supports GTFS times >= 24:00.
    """
    parts = value.split(":")

    hours = int(parts[0])
    minutes = int(parts[1])

    return hours * 60 + minutes


def main():
    print("Downloading LPP GTFS feed...")

    data = urllib.request.urlopen(URL, timeout=60).read()

    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = set(z.namelist())

        routes = read(z, "routes.txt")
        stops = read(z, "stops.txt")
        trips = read(z, "trips.txt")
        stop_times = read(z, "stop_times.txt")

        calendar = (
            read(z, "calendar.txt")
            if "calendar.txt" in names
            else []
        )

        exceptions = (
            read(z, "calendar_dates.txt")
            if "calendar_dates.txt" in names
            else []
        )

    print("Routes:", len(routes))
    print("Stops:", len(stops))
    print("Trips:", len(trips))
    print("Stop times:", len(stop_times))

    # Find the route IDs corresponding to 27, 11 and 25.
    route_ids = {
        r["route_id"]: r["route_short_name"]
        for r in routes
        if r.get("route_short_name", "").strip() in ROUTES
    }

    print("Relevant route IDs:", route_ids)

    # Stop names are compared case-insensitively.
    stop_ids = {
        ORIGIN.casefold(): set()
    }

    for destination in ROUTES.values():
        stop_ids[destination.casefold()] = set()

    for stop in stops:
        name = stop.get("stop_name", "").strip().casefold()

        if name in stop_ids:
            stop_ids[name].add(stop["stop_id"])

    print(
        "Polje stops found:",
        len(stop_ids[ORIGIN.casefold()])
    )

    for destination in ROUTES.values():
        print(
            destination,
            "stops found:",
            len(stop_ids[destination.casefold()])
        )

    # Build service-date lookup.
    services = active_dates(calendar, exceptions)

    print("Services found:", len(services))

    # Group stop times by trip.
    grouped = {}

    for stop_time in stop_times:
        grouped.setdefault(
            stop_time["trip_id"],
            []
        ).append(stop_time)

    # Only keep trips belonging to our three routes.
    trip_info = {
        trip["trip_id"]: trip
        for trip in trips
        if trip["route_id"] in route_ids
    }

    print("Relevant trips:", len(trip_info))

    days = {}

    for trip_id, trip in trip_info.items():

        sequence = sorted(
            grouped.get(trip_id, []),
            key=lambda x: int(
                float(x.get("stop_sequence", "0"))
            )
        )

        # Find Polje on this trip.
        origins = [
            x
            for x in sequence
            if x["stop_id"] in stop_ids[ORIGIN.casefold()]
        ]

        if not origins:
            continue

        line = route_ids[trip["route_id"]]
        destination_name = ROUTES[line]

        destination_ids = stop_ids[
            destination_name.casefold()
        ]

        destinations = [
            x
            for x in sequence
            if x["stop_id"] in destination_ids
        ]

        for origin in origins:

            origin_sequence = int(
                float(origin["stop_sequence"])
            )

            # Only destinations AFTER Polje count.
            after = [
                destination
                for destination in destinations
                if int(
                    float(destination["stop_sequence"])
                ) > origin_sequence
            ]

            if not after:
                continue

            destination = after[0]

            departure = origin["departure_time"]
            arrival = destination["arrival_time"]

            item = {
                "dep": departure[:5],
                "arr": arrival[:5],
            }

            # Add this trip to every date on which its
            # service_id operates.
            for service_day in services.get(
                trip["service_id"],
                []
            ):
                days.setdefault(
                    service_day,
                    {}
                ).setdefault(
                    line,
                    []
                ).append(item)

            break

    # Sort each day's buses chronologically.
    for service_day in days:
        for line in days[service_day]:
            days[service_day][line].sort(
                key=lambda x: (
                    mins(x["dep"]),
                    mins(x["arr"]),
                )
            )

    # Remove duplicate identical departures.
    for service_day in days:
        for line in days[service_day]:
            unique = []
            seen = set()

            for bus in days[service_day][line]:
                key = (
                    bus["dep"],
                    bus["arr"],
                )

                if key not in seen:
                    seen.add(key)
                    unique.append(bus)

            days[service_day][line] = unique

    output = {
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "source": URL,

        "days": days,
    }

    with open(
        "data.json",
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            output,
            f,
            separators=(",", ":")
        )

    print(
        "Generated",
        sum(
            len(lines)
            for lines in days.values()
        ),
        "route/day combinations."
    )

    print(
        "Dates generated:",
        len(days)
    )


if __name__ == "__main__":
    main()
```
