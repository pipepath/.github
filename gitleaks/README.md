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
2. Describe el motivo en `description`, de forma genérica. Este repositorio es público: la ruta, los commits, las regex y la descripción quedan visibles para cualquiera, así que no incluyas detalles internos del repositorio.
3. Ancla cada ruta con `^…$` y combínala con `commits`, `regexes` o `targetRules`; con `commits`, `regexes` o `stopwords` usa `condition = "AND"`. Una ruta sola no pasa el linter. Cada clave va en una sola línea que se pueda leer sola como TOML, y ni las rutas ni las regex pueden ser comodines (`.*`, `.+`).
4. Los archivos de `allow/` solo pueden tener comentarios y tablas `[[allowlists]]`; `[extend]`, `[[rules]]` y `[allowlist]` hacen fallar la CI.

El criterio completo está en el punto «Excepciones de gitleaks», bajo «Integración continua», de [`../.claude/skills/repo-standards/SKILL.md`](../.claude/skills/repo-standards/SKILL.md).

## Comandos

Revisar los archivos de `allow/` (necesita Python 3.11 o superior):

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

Comprobar que la excepción de `spawn-control` conserva su ancla de encabezado: un JWT con otro `kid`, o en otra ruta, sigue siendo un hallazgo (arma los tokens al ejecutar; necesita Docker):

```bash
bash gitleaks/tests/scan_anchor.sh
```

## Desarrollo

Un cambio en `base.toml` o en `allow/` se prueba con los cuatro comandos anteriores; la CI los corre en el job `gitleaks-config`. La imagen de gitleaks de `load_check.sh` debe ser la misma que usa el workflow central.

## Mapa del código

- `base.toml`: configuración base.
- `allow/`: una excepción por repositorio.
- `empty.gitleaksignore`: archivo vacío.
- `check_allow.py`: revisa que `allow/` solo tenga comentarios y tablas `[[allowlists]]`.
- `load_check.sh`: carga cada configuración compuesta en gitleaks.
- `tests/`: `run.sh`, los archivos malos de `bad/` que el linter debe rechazar y `scan_anchor.sh`, que escanea tokens armados al ejecutar.
