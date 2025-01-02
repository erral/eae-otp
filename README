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

Errore hauek detektatu ditut orain arte:

- AlavaBus eragilearen fitxategia ez da zuzena, beraz deskargatu ostean ezabatu egin behar duzu.
- LurraldeBus Tolosaldea eragilearen fitxategia hutsik dago (!!), beraz bere datuak ez dira agertuko.
