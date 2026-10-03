# Changelog

## 0.1.4

- Corregida la configuració quan Meteocat encara no ha publicat les estacions operatives del dia actual: es consulta automàticament l'últim dia disponible.
- Afegit suport per al codi numèric `2` que l'API retorna per identificar les estacions operatives.

## 0.1.3

- Corregida la consulta d'estacions operatives XEMA per incloure la data que ara exigeix l'API de Meteocat.
- Intervals d'actualització limitats a valors segurs per als plans mensuals XEMA 750 i Predicció 100, amb marge per a configuracions, reintents i reinicis.

## 0.1.2

- S'ha aclarit el flux de configuració en dos passos per indicar que el municipi i l'estació XEMA es poden seleccionar després de validar la clau API.

## 0.1.1

- Nou identificador visual amb transparència i variants d'alta resolució per a Home Assistant.

## 0.1.0

- Primera versió de `meteocat_weather`.
- Observacions essencials de la xarxa XEMA.
- Prediccions municipals horàries i diàries.
- Radar de pluja animat de l'última hora.
- Configuració automàtica i editable de municipi i estació.
- Intervals inicials adaptats a les quotes de l'API.
- Reautenticació, diagnòstics segurs i traduccions en català, castellà i anglès.
