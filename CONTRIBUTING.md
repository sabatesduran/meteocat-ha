# Contribuir

1. Crea una branca des de la branca principal.
2. Mantén els canvis centrats en una sola millora o correcció.
3. Afegeix o actualitza proves i traduccions quan correspongui.
4. Executa abans d'obrir una pull request:

```bash
ruff check .
ruff format --check .
pytest
python -m compileall -q custom_components
```

No incloguis claus API, respostes amb dades personals ni fitxers de configuració
reals de Home Assistant als commits o incidències.
