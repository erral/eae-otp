import json
import re
import urllib.request
import os

# GTFS URLs

## EAE
url_eae_gtfs = "https://s3.itbatera.euskadi.eus/02-pro-e3525cfb1b3d99109c5220a2b24bcb30-inet/transport/moveuskadi/data-index-gtfs.json"
url_eae_realtime = "https://s3.itbatera.euskadi.eus/02-pro-e3525cfb1b3d99109c5220a2b24bcb30-inet/transport/moveuskadi/data-index-gtfs-rt.json"


## Nafarroa
url_irunea = "https://transitfeeds.com/p/transporte-urbano-comarcal-de-pamplona/499/latest/download"
url_nafarroa = "https://datosabiertos.navarra.es/dataset/ebfb5edd-0cd9-4b31-b0d9-8bc2d25e2493/resource/d3c1c89a-5d4c-4c25-97b5-66da663d3691/download/gtfs.zip"

## Pirinio Atlantikoak
url_pirinio_atlantikoak = "https://www.pigma.org/public/opendata/nouvelle_aquitaine_mobilites/publication/pyrenees_atlantiques-aggregated-gtfs.zip"


# OSM URLs
url_geofabrik_eae = "https://download.geofabrik.de/europe/spain/pais-vasco-latest.osm.pbf"
url_geofabrik_nafarroa = "https://download.geofabrik.de/europe/spain/navarra-latest.osm.pbf"
url_geofabrik_akitania = (
    "https://download.geofabrik.de/europe/france/aquitaine-latest.osm.pbf"
)

# Constants for real time GTFS files

VEHICLE_POSITION = 1
ALERTS = 2
TRIP_UPDATES = 3


def slugify(name):
    """remove spaces and special chars"""
    return re.sub(r"\W+", "-", name).strip("-")


def validate(filename, file_type):
    """validate wether the GTFS file is correct. Delete if incorrect"""
    if not os.stat(filename).st_size:
        # File is empty, let's delete this one...
        os.remove(filename)
        print(f"Is empty. Deleted file: {filename}")


def download_file(url, file_type, output_filename_append='', suffix=''):
    """ generic function to download and write files into disk """
    sock = urllib.request.urlopen(url)
    filename = url.split('/')[-1]
    raw_data = sock.read()
    full_filename = f"eae/{file_type}-{output_filename_append}-{filename}{suffix}"
    with open(full_filename, "wb") as fp:
        fp.write(raw_data)
        print(f"File written: {full_filename}")
        validate(full_filename, file_type)

def download_osm():
    """ download OSM files """
    for url in [url_geofabrik_eae, url_geofabrik_nafarroa]:
        download_file(url, 'osm')

    print('OSM data downloaded and ready')


def download_gtfs_files():
    """ download all GTFS files"""
    download_gtfs_eae()
    download_gtfs_nafarroa()
    # download_gtfs_pirinio_atlantikoak()

def download_gtfs_eae():
    """ download and unzip the GTFS formatted files"""
    sock = urllib.request.urlopen(url_eae_gtfs)
    json_data = json.load(sock)
    for operator, items in json_data.get('data', {}).items():
        for i, item in enumerate(items):
            gtfs_url = item.get('url')
            download_file(gtfs_url, "gtfs", f"{slugify(operator)}-{i}")

    print("Transport data downloaded and ready")

def download_gtfs_nafarroa():
    """ download files from nafarroa"""
    for i, url in enumerate([url_nafarroa, url_irunea]):
        download_file(url, 'gtfs', f'nafarroa-{i}', suffix='zip')

def download_gtfs_pirinio_atlantikoak():
    """ download files from atlantic pyrenees"""
    download_file(url_pirinio_atlantikoak, 'gtfs')


def get_operator(item):
    url = item.get('url')
    url_parts = url.split('/')
    return url_parts[-2]

def get_file_format(item):
    url = item.get('url')
    url_parts = url.split('/')
    filename = url_parts[-1]

    if filename.find('alert') != -1:
        return ALERTS
    elif filename.find('position') != -1:
        return VEHICLE_POSITION
    elif filename.find("trip") != -1:
        return TRIP_UPDATES


def build_updater(item):
    """ build real time updater stanza from EAE information"""
    operator = get_operator(item)
    fileformat = get_file_format(item)
    updater = {}
    if fileformat == VEHICLE_POSITION:
        updater = {
            "type": "vehicle-positions",
            "url": item.get('url'),
            "feedId": operator,
            "frequencySec": 60,
        }
    elif fileformat == ALERTS:
        updater = {
            "type": "real-time-alerts",
            "frequencySec": 30,
            "url": item.get('url'),
            "feedId": operator,
        }
    elif fileformat == TRIP_UPDATES:
        updater = {
            "type": "stop-time-updater",
            "frequencySec": 60,
            "backwardsDelayPropagationType": "REQUIRED_NO_DATA",
            "url": item.get('url'),
            "feedId": operator,
        }
    return updater

def download_and_build_rt_feed():
    sock = urllib.request.urlopen(url_eae_realtime)
    data = json.load(sock)

    rt_feed = {
        "updaters": []
    }


    for _, items in data.get('data', {}).items():
        for item in items:
            updater = build_updater(item)
            if updater:
                rt_feed['updaters'].append(updater)

    with open('eae/router-config.json', 'w') as fp:
        json.dump(rt_feed, fp)

        print('Real time router config written')

if __name__ == '__main__':
    download_osm()
    download_gtfs_files()
    download_and_build_rt_feed()
