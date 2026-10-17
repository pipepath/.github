# repo-standards

Copia del verificador del estándar de repositorios de Pipepath, para quien mantiene el check central de la organización.

## Qué es esta carpeta

Contiene `verify.py` y `standards/` (el verificador), `gitleaks.toml` y `gitleaks_config.py` (la configuración del escaneo de secretos) y `VERSION`. Es una copia idéntica byte a byte de los archivos del skill `repo-standards` del hub de la organización (repositorio privado `workspaces-hub`). Los ejecuta el workflow `.github/workflows/repo-standards.yml`.

Nadie la edita a mano. La reemplaza, mediante un PR, la sección «Publicar el verificador central» de `/sync-rules` del hub. Un cambio al verificador se hace en el hub y se publica aquí con ese flujo.

## `VERSION`

Es el commit del hub del que salen los archivos de la copia, y el valor que el workflow pasa al verificador con `--version`. La revisión `skill-version` falla en un repositorio cuya copia de `.claude/skills/repo-standards/VERSION` sea distinta. Este repositorio tiene esa copia, así que su propio `VERSION` y el de `.claude/skills/repo-standards/` deben coincidir.

## Escaneo de secretos

El escaneo central de gitleaks usa la configuración que se mantiene en este repositorio, no la del repositorio que llama.

## Comandos

Verificar un repositorio (el de la raíz, en este caso):

```bash
python3 -I repo-standards/verify.py . --version "$(cat repo-standards/VERSION)"
```
