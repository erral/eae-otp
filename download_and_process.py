import json
import re
import urllib.request
import os

url = "https://s3.itbatera.euskadi.eus/02-pro-e3525cfb1b3d99109c5220a2b24bcb30-inet/transport/moveuskadi/data-index-gtfs.json"

url_realtime = "https://s3.itbatera.euskadi.eus/02-pro-e3525cfb1b3d99109c5220a2b24bcb30-inet/transport/moveuskadi/data-index-gtfs-rt.json"


url_geofabrik = "https://download.geofabrik.de/europe/spain/pais-vasco-latest.osm.pbf"


def download_osm():
    """ download OSM file"""
    sock = urllib.request.urlopen(url)
    data = sock.read()
    with open("eae/osm.pbf", 'wb') as fp:
        fp.write(data)

    print('OSM data downloaded and ready')

def slugify(name):
    """ remove spaces and special chars"""
    return re.sub(r'\W+', '-', name).strip('-')

def validate(filename):
    """ validate wether the file is correct. Delete if incorrect"""
    if not os.stat(filename).st_size:
        # File is empty, let's delete this one...
        os.remove(filename)
        print(f'Is empty. Deleted file: {filename}')

def download_gtfs():
    """ download and unzip the GTFS formatted files"""

    sock = urllib.request.urlopen(url)
    json_data = json.load(sock)
    for operator, items in json_data.get('data', {}).items():
        for i, item in enumerate(items):
            gtfs_url = item.get('url')
            gtfs_sock = urllib.request.urlopen(gtfs_url)
            raw_gtfs_data = gtfs_sock.read()
            filename = f'eae/gtfs-{slugify(operator)}-{i}.zip'
            with open(filename, 'wb') as fp:
                fp.write(raw_gtfs_data)

            validate(filename)

            print(f"File downloaded: {slugify(operator)} {i}")

    print("Transport data downloaded and ready")

VEHICLE_POSITION = 1
ALERTS = 2
TRIP_UPDATES = 3


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

def download_and_build_rt_feed():
    sock = urllib.request.urlopen(url_realtime)
    data = json.load(sock)

    rt_feed = {
        "updaters": []
    }


    for _, items in data.get('data', {}).items():
        for item in items:
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
            if updater:
                rt_feed['updaters'].append(updater)

    with open('eae/router-config.json', 'w') as fp:
        json.dump(rt_feed, fp)

        print('router config written')

if __name__ == '__main__':
    download_osm()
    download_gtfs()
    download_and_build_rt_feed()
