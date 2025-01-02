import json
import re
import urllib.request
import os

url = "https://s3.itbatera.euskadi.eus/02-pro-e3525cfb1b3d99109c5220a2b24bcb30-inet/transport/moveuskadi/data-index-gtfs.json"

url_realtime = "https://s3.itbatera.euskadi.eus/02-pro-e3525cfb1b3d99109c5220a2b24bcb30-inet/transport/moveuskadi/data-index-gtfs-rt.json"


url_geofabrik = "https://download.geofabrik.de/europe/spain/pais-vasco-latest.osm.pbf -o eae.pbf"


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


if __name__ == '__main__':
    # download_osm()
    download_gtfs()
