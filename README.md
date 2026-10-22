# Scraping de l'Agenda Cultural

Projecte de la Pràctica 1 de Tipologia i cicle de vida de les dades: descoberta d'URL d'esdeveniments de l'[Agenda Cultural de Catalunya](https://agenda.cultura.gencat.cat/) mitjançant navegació amb Playwright.

## Estat actual

Pas 1 d'inspecció completat i pas 2 de preparació implementat. El punt d'entrada valida la configuració i mostra les rutes. Encara no obre el navegador, no descobreix URL i no crea ni modifica el CSV.

El [pla del projecte](PLAN.md) detalla els passos següents. La [inspecció de la web](docs/INSPECCIO_AGENDA.md) recull el recorregut, la paginació i els selectors observats.

## Decisions d'arquitectura

El procés es divideix en dues fases que compartiran `dataset/events.csv`:

1. **Descoberta:** Playwright recorrerà totes les pàgines del cercador públic i afegirà només URL noves a la columna `url`. El CSV serà acumulatiu i no tindrà duplicats normalitzats.
2. **Enriquiment (TODO):** llegirà aquestes URL i completarà les columnes de cada fila. Aquesta fase no forma part de la implementació actual.

`main.py` serà el punt d'entrada. La classe `Browser` de `browser.py` gestionarà Playwright; `discover.py` contindrà la navegació i l'extracció específiques de l'Agenda. Els dos últims mòduls encara estan pendents.

La descoberta prevista guardarà el progrés després de cada pàgina i permetrà tornar a començar sense duplicar files. També preservarà les columnes que incorpori l'enriquiment futur. Aquest comportament encara s'ha d'implementar.

L'extracció es farà a través de la web pública, sense utilitzar l'API de l'Agenda. «Tots els esdeveniments» es refereix als exposats pel cercador en executar-lo; no és una garantia de recuperar tot l'històric.

## Fitxers actuals

```text
.
├── README.md
├── PLAN.md
├── requirements.txt
├── .env.example
├── .env                       # Local; exclòs de Git.
├── .gitignore
├── docs/
│   └── INSPECCIO_AGENDA.md
├── source/
│   └── main.py
└── dataset/
    └── .gitkeep                # Manté la carpeta al repositori fins a tenir dades.
```

La carpeta `.venv/` conté l'entorn virtual local i també està exclosa de Git. `events.csv` es crearà quan s'implementi la persistència; no es publica ara un CSV buit com si fos un resultat.

## Instal·lació

Requereix Python 3.10 o superior. L'entorn local d'aquest projecte es prepara amb Python 3.14.6 i Chromium. Les dependències directes estan fixades a `requirements.txt`: Playwright 1.64.0 i python-dotenv 1.2.4.

Des de l'arrel del repositori, en macOS o Linux:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install chromium
```

Comprova que `python3` és una versió compatible abans de crear l'entorn. En aquest Mac, el Python del sistema és 3.9.6; per reproduir l'entorn local, utilitza `/opt/homebrew/bin/python3.14 -m venv .venv` en lloc de la primera ordre.

La instal·lació de Chromium és un pas separat: instal·lar el paquet Python de Playwright no instal·la automàticament el navegador. Consulta les [instruccions oficials de Playwright](https://playwright.dev/python/docs/library).

## Configuració

Si encara no tens un `.env`, copia `.env.example` a `.env` a l'arrel del repositori. No sobreescriguis un `.env` local que ja contingui la teva configuració.

```dotenv
URL=https://agenda.cultura.gencat.cat/
```

El programa llegeix explícitament aquest fitxer: no busca configuracions en altres carpetes ni pren `URL` de les variables de la sessió. La URL ha de ser absoluta, HTTP o HTTPS i sense credencials ni espais.

Si falta el fitxer, falta la variable o la URL no és vàlida, es mostra un error per la sortida d'errors i el procés retorna el codi 2. No es modifica cap CSV.

## Execució actual

Amb l'entorn virtual activat, des de l'arrel:

```sh
python source/main.py
```

Sortida esperada amb la configuració d'exemple:

```text
Configuració validada correctament.
URL inicial: https://agenda.cultura.gencat.cat/
CSV previst: <arrel del repositori>/dataset/events.csv
Pas 2 completat. La descoberta encara no està implementada.
```

L'execució correcta retorna el codi 0. En aquest pas l'script no admet paràmetres de configuració per línia d'ordres: la URL es defineix a `.env`. Les rutes es calculen respecte de `main.py`, de manera que també es pot executar des d'una altra carpeta utilitzant les rutes absolutes a l'intèrpret i a l'script.

## PyCharm

Selecciona `.venv/bin/python` dins d'aquest repositori com a intèrpret del projecte. Executa `source/main.py`. El directori de treball no afecta la localització de `.env` ni la ruta prevista del CSV.

## TODO de lliurament

- Completar la classe del navegador, la descoberta i la persistència segons el pla.
- Enriquiment de les fitxes: pendent, fora de l'abast actual.
- Incorporar els noms dels dos integrants del grup abans del lliurament.
- Afegir el dataset resultant i el DOI de Zenodo quan estiguin disponibles.
