# EAEko garraio datu-publikoekin egindako OpenTripPlanner planifikatzailea

EAEko administrazioak argitaratzen dituen datu-publikoen artean EAEko garraio eragileen ordutegiak daude.

Horiek jarraituz, teorian, garraio planifikatzaile multi-modal bat egiteko gai izango ginateke.

Baina badakizue, Homer Simpsonek esan zuen moduan [Teorian komunismoak ere funtzionatzen du. Teorian](https://youtu.be/lgi1LFVWurg?si=Tu95mBpwTbI6UxKn&t=23)

Atrebitzen zara datuak benetakoak diren probatzera?

## Instalatu

0. Deskargatu kode errepositorio hau
1. Exekutatu komando hau termina baten datuak deskargatzeko:

```bash
python download_and_process.py
```

Scriptak GTFS eta OSM fitxategiak deskargatu, egiaztatu eta `eae/` karpetan uzten ditu. Gainera, `eae/build-config.json` eta `eae/router-config.json` fitxategiak sortzen ditu, GTFS bakoitzari `feedId` egonkor bat esleituz eta denbora errealeko feederak feed horiekin lotuz.

OSM fitxategiak berriro deskargatu nahi ez badituzu (handiak dira eta gutxitan aldatzen dira):

```bash
python download_and_process.py --skip-osm
```

GTFS fitxategiak aurrez deskargatuta badituzu, `--skip-gtfs` erabil dezakezu.

2. Exekutatu komando hau planifikatzailearen grafoa sortzeko:

```bash
docker run --rm \
 -e JAVA_TOOL_OPTIONS='-Xmx8g' \
 -v "$(pwd)/eae:/var/opentripplanner" \
 docker.io/opentripplanner/opentripplanner:latest --build --save
```

3. Exekutatu komando hau planifikatzeailea martxan jartzeko:

```bash
docker run -it --rm -p 8080:8080 \
    -e JAVA_TOOL_OPTIONS='-Xmx8g' \
    -v "$(pwd)/eae:/var/opentripplanner" \
    docker.io/opentripplanner/opentripplanner:latest --load --serve
```

## Petau itxe xauk!

Ja! Eutsi frakei!

Ba agian gure agintariek eta garraiobideek argitaratzen dituzten GTFS formatuko fitxategiak ez dira zuzenak!

Scriptak deskargatutako GTFS fitxategiak automatikoki egiaztatzen ditu: zip hondatua, hutsik dagoena edo derrigorrezko fitxategiak falta dituena ezabatu eta errore mezua ematen du.

Hala ere, baliozkotze horrek ezin ditu arazo semantikoak detektatu (adibidez, ordutegiak edo ibilbideak gaizki egotea). Halakoak OTPren grafoa sortzean agertzen diren logetan ikusiko dituzu.

Proiektuaren hasieran arazo hauek detektatu ziren, gaur egun konponduta daudela dirudien arren:

- AlavaBus eragilearen fitxategia ez zen zuzena.
- LurraldeBus Tolosaldea eragilearen fitxategia hutsik zegoen.
