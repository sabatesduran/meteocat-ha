# Meteocat Weather per a Home Assistant

Integració lleugera instal·lable amb HACS que combina les dades oficials de
[Meteocat](https://www.meteo.cat/) amb els components natius de Home Assistant.
No entra en conflicte amb la integració comunitària `meteocat`: aquest projecte
utilitza el domini propi `meteocat_weather`.

## Funcions

- Entitat **Weather** amb observacions XEMA actuals.
- Predicció municipal **horària (72 h)** i **diària (8 dies)**.
- Sensors de temperatura, humitat, pressió, precipitació, vent, ratxa i hora de
  l'última observació, sempre que l'estació els publiqui.
- Càmera **GIF animada** amb el radar de pluja de l'última hora.
- Selecció automàtica de l'estació XEMA més propera a Home Assistant.
- Municipi i estació editables durant la configuració i des de les opcions.
- Reautenticació de la clau API, memòria cau de les dades del coordinador,
  diagnòstics segurs i traduccions en català, castellà i anglès.

## Requisits

- Home Assistant 2025.12 o posterior.
- Una clau de l'[API de Dades Meteorològiques de Meteocat](https://apidocs.meteocat.gencat.cat/).
- La clau ha de tenir accés als plans **XEMA** i **Predicció**.

El radar utilitza les tessel·les públiques oficials i no consumeix la quota de
la clau API. Com que aquest recurs públic no forma part de l'API REST
documentada, el proveïdor està aïllat a `radar.py` per facilitar-ne el
manteniment si Meteocat canvia les rutes.

## Instal·lació amb HACS

1. A HACS, obre **Integracions**.
2. Obre el menú de tres punts i selecciona **Repositoris personalitzats**.
3. Afegeix `https://github.com/sabatesduran/meteocat-ha` com a tipus **Integració**.
4. Instal·la **Meteocat Weather** i reinicia Home Assistant.
5. Ves a **Configuració → Dispositius i serveis → Afegeix integració**.
6. Cerca **Meteocat Weather** i introdueix la clau API.

### Instal·lació manual

Copia `custom_components/meteocat_weather` dins la carpeta
`config/custom_components/` de Home Assistant i reinicia el servidor.

## Configuració

La primera pantalla demana la clau API i unes coordenades. Per defecte utilitza
les coordenades de Home Assistant. La integració consulta les estacions
operatives, proposa la més propera i permet canviar tant l'estació com el
municipi emprat per a la predicció.

Des de **Configura** es poden modificar:

| Opció | Valors | Predeterminat |
| --- | --- | --- |
| Actualització XEMA | 30, 60, 90 o 180 minuts | Segons quota (habitualment 90 min) |
| Actualització de predicció | 6, 12 o 24 hores | Segons quota (habitualment 24 h) |
| Cobertura del radar | Catalunya o local | Local |
| Historial del radar | 30 o 60 minuts | 60 minuts |

La integració consulta `quotes/v1/consum-actual`, reserva un 20% de marge i tria
automàticament els intervals inicials més ràpids que no haurien de superar la
quota mensual. Si aquesta consulta no està disponible, utilitza 90 minuts per a
XEMA i 24 hores per a les prediccions. Comprova la quota concreta del teu pla
abans de reduir manualment els intervals.

## Targetes del tauler

La integració no requereix cap targeta personalitzada.

### Predicció

```yaml
type: weather-forecast
entity: weather.meteocat_weather
forecast_type: hourly
show_forecast: true
```

El nom exacte de l'entitat dependrà del municipi i de les regles de noms de
Home Assistant.

### Radar animat

```yaml
type: picture-entity
entity: camera.meteocat_radar_de_pluja
camera_view: live
show_name: true
show_state: false
```

El primer GIF pot trigar uns segons perquè descarrega els fotogrames de l'última
hora. A partir d'aquí només s'afegeixen les imatges noves i es reutilitzen el
mapa base i les tessel·les encara vigents.

## Privadesa i errors

- La clau API només es desa al `ConfigEntry` de Home Assistant.
- No s'escriu als logs i queda eliminada dels diagnòstics.
- Les coordenades exactes també queden eliminades dels diagnòstics.
- Els errors `403`, `429`, de xarxa i de servidor es tracten separadament.
- Si una actualització falla, Home Assistant conserva les últimes dades bones.

Per activar logs de depuració:

```yaml
logger:
  logs:
    custom_components.meteocat_weather: debug
```

## Desenvolupament

```bash
python -m pip install pytest ruff
ruff check .
ruff format --check .
pytest
python -m compileall -q custom_components
```

La CI també executa les validacions de HACS i Hassfest. Les proves no necessiten
cap clau API i utilitzen respostes simulades.

## Fonts i atribució

Dades del Servei Meteorològic de Catalunya (Meteocat). Aquest projecte no és un
producte oficial del Servei Meteorològic de Catalunya ni de la Generalitat de
Catalunya.

## Llicència

[Apache License 2.0](LICENSE).
