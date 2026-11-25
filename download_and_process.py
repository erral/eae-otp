#!/usr/bin/env python3
"""Download EAE/Nafarroa transport data and generate the OTP configuration."""

import argparse
import csv
import io
import json
import os
import re
import shutil
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
EAE_DIR = BASE_DIR / "eae"
BUILD_CONFIG_PATH = EAE_DIR / "build-config.json"
ROUTER_CONFIG_PATH = EAE_DIR / "router-config.json"

# GTFS URLs

## EAE
url_eae_gtfs = "https://s3.itbatera.euskadi.eus/02-pro-e3525cfb1b3d99109c5220a2b24bcb30-inet/transport/moveuskadi/data-index-gtfs.json"
url_eae_realtime = "https://s3.itbatera.euskadi.eus/02-pro-e3525cfb1b3d99109c5220a2b24bcb30-inet/transport/moveuskadi/data-index-gtfs-rt.json"

## Nafarroa
# The old transitfeeds.com URL for Pamplona is gone (it answers HTTP 403),
# so only the official Navarra open data feed is downloaded.
url_nafarroa = "https://datosabiertos.navarra.es/dataset/ebfb5edd-0cd9-4b31-b0d9-8bc2d25e2493/resource/d3c1c89a-5d4c-4c25-97b5-66da663d3691/download/gtfs.zip"


# OSM URLs
url_geofabrik_eae = "https://download.geofabrik.de/europe/spain/pais-vasco-latest.osm.pbf"
url_geofabrik_nafarroa = "https://download.geofabrik.de/europe/spain/navarra-latest.osm.pbf"

# Constants for real time GTFS files

VEHICLE_POSITION = 1
ALERTS = 2
TRIP_UPDATES = 3

# Minimum files a GTFS feed must contain to be usable by OTP.
REQUIRED_GTFS_FILES = (
    "agency.txt",
    "stops.txt",
    "routes.txt",
    "trips.txt",
    "stop_times.txt",
)

REQUEST_TIMEOUT = 60
DOWNLOAD_ATTEMPTS = 3
USER_AGENT = "eae-otp-downloader/1.0"


def slugify(name):
    """Remove spaces and special characters."""
    return re.sub(r"\W+", "-", name).strip("-")


def feed_id_from_url(url):
    """Use the operator directory in a feed URL as its feed id.

    EAE publishes static and realtime files under the same operator directory,
    e.g. ``.../lurraldebus/goierrialdea/gtfs_goierrialdea.zip`` and
    ``.../lurraldebus/goierrialdea/gtfsrt_goierrialdea_trip_updates.pb``. Using
    that directory makes the realtime ``feedId`` match the static feed.
    """
    path = urllib.parse.urlparse(url).path
    return slugify(Path(path).parent.name)


def filename_from_url(url):
    """Return the file name of a URL (without the query string)."""
    path = urllib.parse.urlparse(url).path
    return Path(path).name


def normalize_url(url):
    """Percent-encode characters that java.net.URI rejects (e.g. spaces).

    Some EAE realtime URLs contain literal spaces, e.g.
    ``gtfsrt_errenteriako urbanoa_vehicle_positions.pb``. OTP parses the
    router configuration with ``java.net.URI``, which refuses them.
    """
    parts = urllib.parse.urlsplit(url)
    path = urllib.parse.quote(parts.path, safe="/:@!$&'()*+,;=-._~%")
    query = urllib.parse.quote(parts.query, safe="=&?/:@!$'()*+,;-._~%")
    fragment = urllib.parse.quote(parts.fragment, safe="=&?/:@!$'()*+,;-._~%")
    return urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, path, query, fragment)
    )


def fetch_json(url):
    """Fetch and decode a JSON document."""
    request = urllib.request.Request(
        normalize_url(url), headers={"User-Agent": USER_AGENT}
    )
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        return json.load(response)


def download_file(url, destination):
    """Download ``url`` into ``destination``, retrying on transient errors."""
    url = normalize_url(url)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)

    last_error = None
    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                with destination.open("wb") as fp:
                    shutil.copyfileobj(response, fp)
            print(f"Downloaded: {url} -> {destination}")
            return destination
        except urllib.error.HTTPError as exc:
            # Retrying a 4xx response will not help.
            if 400 <= exc.code < 500:
                raise RuntimeError(f"Cannot download {url}: HTTP {exc.code}") from exc
            last_error = exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc

        if destination.exists():
            destination.unlink()
        if attempt < DOWNLOAD_ATTEMPTS:
            delay = 2 ** (attempt - 1)
            print(f"Download failed ({last_error}). Retrying in {delay}s...")
            time.sleep(delay)

    raise RuntimeError(f"Cannot download {url}: {last_error}")


def read_gtfs_table(archive, name):
    """Read a GTFS text file from an open zip archive."""
    with archive.open(name) as fp:
        text = io.TextIOWrapper(fp, encoding="utf-8-sig", newline="")
        return list(csv.DictReader(text))


def feed_last_service_date(archive):
    """Return the latest service date (YYYYMMDD) declared by a GTFS feed."""
    names = {Path(info.filename).name for info in archive.infolist()}

    if "feed_info.txt" in names:
        ends = [
            row.get("feed_end_date", "").strip()
            for row in read_gtfs_table(archive, "feed_info.txt")
        ]
        ends = [end for end in ends if end]
        if ends:
            return max(ends)

    if "calendar.txt" in names:
        ends = [
            row.get("end_date", "").strip()
            for row in read_gtfs_table(archive, "calendar.txt")
        ]
        ends = [end for end in ends if end]
        if ends:
            return max(ends)

    if "calendar_dates.txt" in names:
        last = None
        with archive.open("calendar_dates.txt") as fp:
            reader = csv.DictReader(
                io.TextIOWrapper(fp, encoding="utf-8-sig", newline="")
            )
            for row in reader:
                value = (row.get("date") or "").strip()
                if value and (last is None or value > last):
                    last = value
        return last

    return None


def validate_gtfs(path):
    """Raise an error if a downloaded GTFS file is empty, corrupt or incomplete."""
    path = Path(path)
    if path.stat().st_size == 0:
        raise RuntimeError(f"GTFS file is empty: {path}")

    last_service = None
    try:
        with zipfile.ZipFile(path) as archive:
            corrupt_member = archive.testzip()
            if corrupt_member is not None:
                raise RuntimeError(
                    f"GTFS file is corrupt ({corrupt_member}): {path}"
                )

            members = {Path(info.filename).name: info for info in archive.infolist()}
            missing = [name for name in REQUIRED_GTFS_FILES if name not in members]
            if missing:
                raise RuntimeError(
                    f"GTFS file is incomplete (missing {', '.join(missing)}): {path}"
                )

            empty = [
                name
                for name in REQUIRED_GTFS_FILES
                if members[name].file_size == 0
            ]
            if empty:
                raise RuntimeError(
                    f"GTFS file has empty tables ({', '.join(empty)}): {path}"
                )

            last_service = feed_last_service_date(archive)
    except zipfile.BadZipFile as exc:
        raise RuntimeError(f"GTFS file is not a valid zip archive: {path}") from exc

    print(f"Validated GTFS file: {path}")

    if last_service and last_service < date.today().strftime("%Y%m%d"):
        print(
            f"WARNING: {path.name} has no service after {last_service} "
            f"(today is {date.today().isoformat()}). OTP will import it, but it "
            "will not produce trips for current dates. Ask the data publisher "
            "for an updated feed."
        )


def validate_osm(path):
    """Raise an error if a downloaded OSM file is empty."""
    path = Path(path)
    if path.stat().st_size == 0:
        raise RuntimeError(f"OSM file is empty: {path}")
    print(f"Validated OSM file: {path}")


def validate_file(entry, path):
    """Validate a downloaded file according to its kind."""
    if entry["kind"] == "gtfs":
        validate_gtfs(path)
    else:
        validate_osm(path)


def unique_id(base, used_ids):
    """Return ``base`` or a numbered variant that is not in ``used_ids``."""
    if base not in used_ids:
        used_ids.add(base)
        return base

    suffix = 2
    while f"{base}-{suffix}" in used_ids:
        suffix += 1
    feed_id = f"{base}-{suffix}"
    used_ids.add(feed_id)
    return feed_id


def collect_gtfs_feeds():
    """Return the GTFS feeds to download together with their OTP feed ids."""
    used_ids = set()
    feeds = []

    data = fetch_json(url_eae_gtfs)
    for operator, items in sorted(data.get("data", {}).items()):
        for item in items:
            url = item.get("url")
            if not url:
                continue
            url = normalize_url(url)
            feed_id = unique_id(feed_id_from_url(url), used_ids)
            feeds.append(
                {
                    "kind": "gtfs",
                    "operator": operator,
                    "url": url,
                    "feedId": feed_id,
                    "filename": f"gtfs-{feed_id}.zip",
                }
            )

    nafarroa_id = unique_id("nafarroa", used_ids)
    feeds.append(
        {
            "kind": "gtfs",
            "operator": "Nafarroa",
            "url": url_nafarroa,
            "feedId": nafarroa_id,
            "filename": f"gtfs-{nafarroa_id}.zip",
        }
    )

    return sorted(feeds, key=lambda feed: feed["filename"])


def collect_osm_feeds():
    """Return the OSM files to download."""
    feeds = []
    for url in (url_geofabrik_eae, url_geofabrik_nafarroa):
        feeds.append(
            {
                "kind": "osm",
                "url": url,
                "filename": f"osm-{filename_from_url(url)}",
            }
        )
    return feeds


def get_file_format(url):
    """Detect which kind of realtime GTFS-RT feed a URL points to."""
    name = filename_from_url(url).lower()

    if "alert" in name:
        return ALERTS
    if "position" in name:
        return VEHICLE_POSITION
    if "trip" in name:
        return TRIP_UPDATES
    return None


def build_updater(item, known_feed_ids):
    """Build a router-config updater stanza from an EAE realtime feed entry."""
    url = item.get("url")
    if not url:
        return None
    url = normalize_url(url)

    feed_id = feed_id_from_url(url)
    file_format = get_file_format(url)
    if file_format is None:
        return None

    if feed_id not in known_feed_ids:
        print(f"Skipping realtime feed for unknown operator: {feed_id} ({url})")
        return None

    base = {"url": url, "feedId": feed_id}
    if file_format == VEHICLE_POSITION:
        return {**base, "type": "vehicle-positions", "frequencySec": 60}
    if file_format == ALERTS:
        return {**base, "type": "real-time-alerts", "frequencySec": 30}
    return {
        **base,
        "type": "stop-time-updater",
        "frequencySec": 60,
        "backwardsDelayPropagationType": "REQUIRED_NO_DATA",
    }


def collect_updaters(known_feed_ids):
    """Return the deduplicated realtime updaters for router-config.json."""
    data = fetch_json(url_eae_realtime)

    updaters = {}
    for items in data.get("data", {}).values():
        for item in items:
            updater = build_updater(item, known_feed_ids)
            if updater is None:
                continue
            key = (updater["type"], updater["feedId"], updater["url"])
            updaters[key] = updater

    return sorted(
        updaters.values(),
        key=lambda updater: (updater["type"], updater["feedId"], updater["url"]),
    )


def replace_files(entries, staging_dir, pattern):
    """Remove previous files matching ``pattern`` and move the new ones in."""
    for existing in EAE_DIR.glob(pattern):
        if existing.is_file():
            existing.unlink()

    for entry in entries:
        source = Path(staging_dir) / entry["filename"]
        destination = EAE_DIR / entry["filename"]
        os.replace(source, destination)
        print(f"Installed: {destination}")


def read_json(path):
    """Read a JSON file, returning an empty object when it does not exist."""
    path = Path(path)
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as fp:
        return json.load(fp)


def write_json(path, data):
    """Write JSON atomically and with a stable layout."""
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as fp:
        json.dump(data, fp, indent=2, sort_keys=True, ensure_ascii=False)
        fp.write("\n")
    os.replace(temporary, path)
    print(f"Configuration written: {path}")


def write_build_config(feeds):
    """Write build-config.json with explicit feed ids for every GTFS file."""
    config = read_json(BUILD_CONFIG_PATH)
    config.setdefault(
        "osmDefaults",
        {"timeZone": "Europe/Madrid", "osmTagMapping": "default"},
    )
    config.setdefault("transitModelTimeZone", "Europe/Madrid")
    config["transitFeeds"] = [
        {
            "type": "gtfs",
            "source": feed["filename"],
            "feedId": feed["feedId"],
        }
        for feed in sorted(feeds, key=lambda feed: feed["filename"])
    ]
    write_json(BUILD_CONFIG_PATH, config)


def write_router_config(updaters):
    """Write router-config.json, keeping any manually configured options."""
    config = read_json(ROUTER_CONFIG_PATH)
    config["updaters"] = updaters
    write_json(ROUTER_CONFIG_PATH, config)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-osm",
        action="store_true",
        help="do not download OSM files (reuse the existing ones)",
    )
    parser.add_argument(
        "--skip-gtfs",
        action="store_true",
        help="do not download GTFS files (reuse the existing ones)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    EAE_DIR.mkdir(parents=True, exist_ok=True)

    gtfs_feeds = collect_gtfs_feeds()
    osm_feeds = collect_osm_feeds()

    if args.skip_gtfs:
        missing = [
            feed["filename"]
            for feed in gtfs_feeds
            if not (EAE_DIR / feed["filename"]).exists()
        ]
        if missing:
            raise SystemExit(
                "Missing local GTFS files: "
                + ", ".join(missing)
                + ". Run again without --skip-gtfs."
            )

    # Build the realtime config before downloading anything, so a broken
    # endpoint aborts the run without leaving a half-updated data directory.
    updaters = collect_updaters({feed["feedId"] for feed in gtfs_feeds})

    pending = []
    if not args.skip_gtfs:
        pending.extend(gtfs_feeds)
    if not args.skip_osm:
        pending.extend(osm_feeds)

    if pending:
        staging_dir = Path(tempfile.mkdtemp(prefix=".staging-", dir=EAE_DIR))
        try:
            for entry in pending:
                destination = staging_dir / entry["filename"]
                download_file(entry["url"], destination)
                validate_file(entry, destination)

            if not args.skip_gtfs:
                replace_files(gtfs_feeds, staging_dir, "gtfs-*.zip*")
            if not args.skip_osm:
                replace_files(osm_feeds, staging_dir, "osm-*.pbf")
        finally:
            shutil.rmtree(staging_dir, ignore_errors=True)

    write_build_config(gtfs_feeds)
    write_router_config(updaters)
    print("Transport data downloaded, validated and ready")


if __name__ == "__main__":
    main()
