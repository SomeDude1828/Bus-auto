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
                io.TextIOWrapper(
                    f,
                    "utf-8-sig",
                    newline=""
                )
            )
        )


def mins(value):
    """
    Convert GTFS time into minutes after midnight.

    Supports:
        HH:MM
        HH:MM:SS

    GTFS also allows times >= 24:00.
    Example:
        24:30 -> 1470
    """
    parts = value.split(":")

    hours = int(parts[0])
    minutes = int(parts[1])

    return hours * 60 + minutes


def build_service_dates(calendar, calendar_dates):
    """
    Build the complete set of dates on which each service_id operates.

    calendar.txt:
        Defines normal weekly service.

    calendar_dates.txt:
        exception_type 1 = ADD service
        exception_type 2 = REMOVE service

    This also supports services that have no calendar.txt entry
    and exist only through calendar_dates.txt.
    """

    services = {}

    weekdays = [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]

    print()
    print("Building service calendar...")

    # ---------------------------------------------------------
    # 1. Normal weekly service from calendar.txt
    # ---------------------------------------------------------

    for row in calendar:
        service_id = row["service_id"]

        try:
            start = date.fromisoformat(row["start_date"])
            end = date.fromisoformat(row["end_date"])
        except ValueError:
            print(
                "WARNING: Invalid calendar dates for service:",
                service_id
            )
            continue

        active = services.setdefault(service_id, set())

        current = start

        while current <= end:
            weekday = weekdays[current.weekday()]

            if row.get(weekday) == "1":
                active.add(current.isoformat())

            current += timedelta(days=1)

    # ---------------------------------------------------------
    # 2. Apply calendar_dates.txt exceptions
    # ---------------------------------------------------------

    additions = 0
    removals = 0

    for row in calendar_dates:
        service_id = row["service_id"]
        service_dates = services.setdefault(
            service_id,
            set()
        )

        service_date = row["date"]
        exception_type = row["exception_type"]

        if exception_type == "1":
            service_dates.add(service_date)
            additions += 1

        elif exception_type == "2":
            service_dates.discard(service_date)
            removals += 1

    print("Calendar services:", len(services))
    print("Added exception dates:", additions)
    print("Removed exception dates:", removals)

    # Remove empty services.
    services = {
        service_id: dates
        for service_id, dates in services.items()
        if dates
    }

    print(
        "Services with active dates:",
        len(services)
    )

    return services


def main():

    print("========================================")
    print("LPP GTFS timetable builder")
    print("========================================")
    print()

    # ---------------------------------------------------------
    # Download GTFS
    # ---------------------------------------------------------

    print("Downloading LPP GTFS feed...")

    request = urllib.request.Request(
        URL,
        headers={
            "User-Agent": "Bus-auto timetable builder"
        }
    )

    with urllib.request.urlopen(
        request,
        timeout=60
    ) as response:
        data = response.read()

    print(
        "Downloaded:",
        round(len(data) / 1024 / 1024, 2),
        "MB"
    )

    # ---------------------------------------------------------
    # Read GTFS files
    # ---------------------------------------------------------

    with zipfile.ZipFile(
        io.BytesIO(data)
    ) as z:

        names = set(z.namelist())

        required_files = [
            "routes.txt",
            "stops.txt",
            "trips.txt",
            "stop_times.txt",
        ]

        for filename in required_files:
            if filename not in names:
                raise RuntimeError(
                    f"GTFS feed is missing {filename}"
                )

        routes = read(z, "routes.txt")
        stops = read(z, "stops.txt")
        trips = read(z, "trips.txt")
        stop_times = read(z, "stop_times.txt")

        calendar = (
            read(z, "calendar.txt")
            if "calendar.txt" in names
            else []
        )

        calendar_dates = (
            read(z, "calendar_dates.txt")
            if "calendar_dates.txt" in names
            else []
        )

    print()
    print("Routes:", len(routes))
    print("Stops:", len(stops))
    print("Trips:", len(trips))
    print("Stop times:", len(stop_times))
    print("Calendar rows:", len(calendar))
    print("Calendar exception rows:", len(calendar_dates))

    # ---------------------------------------------------------
    # Find relevant routes
    # ---------------------------------------------------------

    route_ids = {}

    for route in routes:

        short_name = route.get(
            "route_short_name",
            ""
        ).strip()

        if short_name in ROUTES:
            route_ids[route["route_id"]] = short_name

    print()
    print("Relevant route IDs:")

    for route_id, short_name in route_ids.items():
        print(
            " ",
            short_name,
            "->",
            route_id
        )

    # ---------------------------------------------------------
    # Find stops
    # ---------------------------------------------------------

    stop_ids = {
        ORIGIN.casefold(): set()
    }

    for destination in ROUTES.values():
        stop_ids[destination.casefold()] = set()

    for stop in stops:

        name = stop.get(
            "stop_name",
            ""
        ).strip().casefold()

        if name in stop_ids:
            stop_ids[name].add(
                stop["stop_id"]
            )

    print()
    print("Relevant stops:")

    print(
        " Polje:",
        len(stop_ids[ORIGIN.casefold()])
    )

    for destination in ROUTES.values():
        print(
            f" {destination}:",
            len(
                stop_ids[
                    destination.casefold()
                ]
            )
        )

    # ---------------------------------------------------------
    # Build service calendar
    # ---------------------------------------------------------

    services = build_service_dates(
        calendar,
        calendar_dates
    )

    # ---------------------------------------------------------
    # Group stop_times by trip
    # ---------------------------------------------------------

    print()
    print("Grouping stop times...")

    grouped = {}

    for stop_time in stop_times:

        trip_id = stop_time["trip_id"]

        grouped.setdefault(
            trip_id,
            []
        ).append(stop_time)

    # ---------------------------------------------------------
    # Keep only relevant trips
    # ---------------------------------------------------------

    trip_info = {
        trip["trip_id"]: trip
        for trip in trips
        if trip.get("route_id") in route_ids
    }

    print(
        "Relevant trips:",
        len(trip_info)
    )

    # ---------------------------------------------------------
    # Build timetable
    #
    # IMPORTANT:
    #
    # days[date][route] is ALWAYS one list.
    #
    # This prevents duplicate JSON keys like:
    #
    # "27": [...]
    # "27": [...]
    #
    # Instead all 27 buses get merged:
    #
    # "27": [...all buses...]
    # ---------------------------------------------------------

    days = {}

    trip_count = 0
    timetable_count = 0

    for trip_id, trip in trip_info.items():

        sequence = sorted(
            grouped.get(
                trip_id,
                []
            ),
            key=lambda x: int(
                float(
                    x.get(
                        "stop_sequence",
                        "0"
                    )
                )
            )
        )

        if not sequence:
            continue

        # -----------------------------------------------------
        # Find Polje
        # -----------------------------------------------------

        origins = [
            stop_time
            for stop_time in sequence
            if stop_time["stop_id"]
            in stop_ids[
                ORIGIN.casefold()
            ]
        ]

        if not origins:
            continue

        line = route_ids[
            trip["route_id"]
        ]

        destination_name = ROUTES[line]

        destination_ids = stop_ids[
            destination_name.casefold()
        ]

        # -----------------------------------------------------
        # Find destination after Polje
        # -----------------------------------------------------

        destinations = [
            stop_time
            for stop_time in sequence
            if stop_time["stop_id"]
            in destination_ids
        ]

        if not destinations:
            continue

        found_trip = False

        for origin in origins:

            origin_sequence = int(
                float(
                    origin["stop_sequence"]
                )
            )

            after = [
                destination
                for destination in destinations
                if int(
                    float(
                        destination[
                            "stop_sequence"
                        ]
                    )
                ) > origin_sequence
            ]

            if not after:
                continue

            destination = after[0]

            departure = origin.get(
                "departure_time"
            )

            arrival = destination.get(
                "arrival_time"
            )

            if not departure or not arrival:
                continue

            item = {
                "dep": departure[:5],
                "arr": arrival[:5],
            }

            # -------------------------------------------------
            # Add to EVERY date this service operates.
            #
            # setdefault ensures routes are merged rather
            # than creating duplicate JSON keys.
            # -------------------------------------------------

            service_dates = services.get(
                trip.get("service_id"),
                set()
            )

            for service_day in service_dates:

                route_day = days.setdefault(
                    service_day,
                    {}
                )

                route_buses = route_day.setdefault(
                    line,
                    []
                )

                route_buses.append(item)

                timetable_count += 1

            found_trip = True
            break

        if found_trip:
            trip_count += 1

    # ---------------------------------------------------------
    # Sort and deduplicate
    # ---------------------------------------------------------

    print()
    print("Sorting and merging timetable...")

    for service_day in days:

        for line in days[service_day]:

            buses = days[
                service_day
            ][line]

            # Remove exact duplicates.
            unique = []
            seen = set()

            for bus in buses:

                key = (
                    bus["dep"],
                    bus["arr"],
                )

                if key in seen:
                    continue

                seen.add(key)
                unique.append(bus)

            # Sort by departure first,
            # arrival second.
            unique.sort(
                key=lambda x: (
                    mins(x["dep"]),
                    mins(x["arr"]),
                )
            )

            days[
                service_day
            ][line] = unique

    # ---------------------------------------------------------
    # Sort dates and routes for clean JSON
    # ---------------------------------------------------------

    sorted_days = {}

    for service_day in sorted(days):

        sorted_days[service_day] = {}

        for line in sorted(
            days[service_day],
            key=lambda x: int(x)
        ):

            sorted_days[
                service_day
            ][line] = days[
                service_day
            ][line]

    # ---------------------------------------------------------
    # Print useful verification
    # ---------------------------------------------------------

    print()
    print("========================================")
    print("Verification")
    print("========================================")

    print(
        "Dates generated:",
        len(sorted_days)
    )

    print(
        "Trips converted:",
        trip_count
    )

    print(
        "Timetable entries:",
        timetable_count
    )

    # Check October 6 specifically.
    test_date = "20261006"

    print()

    if test_date in sorted_days:

        print(
            "SUCCESS:",
            test_date,
            "exists."
        )

        for line in ["27", "11", "25"]:

            buses = sorted_days[
                test_date
            ].get(
                line,
                []
            )

            print(
                f" Route {line}:",
                len(buses),
                "buses"
            )

            # Show morning buses.
            morning = [
                bus
                for bus in buses
                if mins(bus["arr"]) <= 600
            ]

            for bus in morning[:10]:

                print(
                    "   ",
                    bus["dep"],
                    "->",
                    bus["arr"]
                )

    else:

        print(
            "WARNING:",
            test_date,
            "is NOT present!"
        )

    # ---------------------------------------------------------
    # Write JSON
    # ---------------------------------------------------------

    output = {
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "source": URL,

        "days": sorted_days,
    }

    with open(
        "data.json",
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            output,
            f,
            ensure_ascii=False,
            separators=(",", ":")
        )

    print()
    print("========================================")
    print("DONE")
    print("========================================")

    print(
        "Generated data.json"
    )

    print(
        "Route/day combinations:",
        sum(
            len(routes)
            for routes in sorted_days.values()
        )
    )


if __name__ == "__main__":
    main()
