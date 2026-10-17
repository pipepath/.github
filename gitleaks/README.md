# gitleaks

Configuración del escaneo de secretos que el workflow central corre sobre todos los repositorios de la organización, para quien mantiene un repositorio y necesita una excepción.

## Qué hay aquí

- `base.toml`: las reglas por defecto de gitleaks, sin nada más.
- `allow/<repo>.toml`: las excepciones de un repositorio. Hoy existen `workspaces-hub`, `spawn-workspace`, `spawn-control` y `brand-app`.
- `empty.gitleaksignore`: un archivo vacío. El workflow borra el `.gitleaksignore` del repositorio que llama y además pasa este archivo en `--gitleaks-ignore-path`, porque gitleaks carga el `.gitleaksignore` del repositorio aunque se le indique otro.
- `check_allow.py`, `load_check.sh` y `tests/`: las comprobaciones que corre la CI de este repositorio sobre los archivos de `allow/` y sus pruebas.

## Cómo se usa

El workflow central une `base.toml` con `allow/<nombre>.toml` (si existe), donde `<nombre>` es el repositorio sin el prefijo `pipepath/`, y escanea el historial completo del repositorio que llama. Otros dueños u otros nombres reciben solo `base.toml`.

El escaneo central ignora el `.gitleaks.toml` del repositorio, su `.gitleaksignore` y los comentarios `gitleaks:allow` en línea. La única forma de silenciar un falso positivo es una entrada en este repositorio.

## Cómo pedir una excepción

1. Abre un PR a este repositorio que agregue una entrada `[[allowlists]]` en `allow/<repo>.toml` (el archivo se crea si no existe).
2. Antepón a cada entrada un comentario con el motivo.
3. Ancla cada ruta con `^…$` y combínala con `commits`, `regexes` o `targetRules`; con `commits`, `regexes` o `stopwords` usa `condition = "AND"`. Una ruta sola no pasa el linter. Los valores van en una sola línea, y las barras invertidas solo dentro de cadenas literales `'''…'''`.
4. Los archivos de `allow/` solo pueden tener comentarios y tablas `[[allowlists]]`; `[extend]`, `[[rules]]` y `[allowlist]` hacen fallar la CI.

El criterio completo está en la sección «Excepciones de gitleaks» del skill `repo-standards` del hub de la organización (repositorio privado `workspaces-hub`).

## Comandos

Revisar los archivos de `allow/` (necesita Python 3):

```bash
python3 -I gitleaks/check_allow.py
```

Probar el linter (cada archivo de `tests/bad/` debe fallar y los de `allow/` deben pasar):

```bash
bash gitleaks/tests/run.sh
```

Cargar la configuración base y cada archivo de `allow/` en la imagen fijada de gitleaks, contra un directorio vacío (necesita Docker):

```bash
bash gitleaks/load_check.sh
```

## Desarrollo

Un cambio en `base.toml` o en `allow/` se prueba con los tres comandos anteriores; la CI los corre en el job `gitleaks-config`. La imagen de gitleaks de `load_check.sh` debe ser la misma que usa el workflow central.

## Mapa del código

- `base.toml`: configuración base.
- `allow/`: una excepción por repositorio.
- `empty.gitleaksignore`: archivo vacío.
- `check_allow.py`: revisa que `allow/` solo tenga comentarios y tablas `[[allowlists]]`.
- `load_check.sh`: carga cada configuración compuesta en gitleaks.
- `tests/`: `run.sh` y los archivos malos de `bad/` que el linter debe rechazar.
