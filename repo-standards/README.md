# repo-standards

Copia del verificador del estándar de repositorios de Pipepath, para quien mantiene el check central de la organización.

## Qué es esta carpeta

Contiene `verify.py` y `standards/` (el verificador) y `VERSION`. Es una copia idéntica byte a byte de los archivos del skill `repo-standards` del hub de la organización (repositorio privado `workspaces-hub`). Los ejecuta el workflow `.github/workflows/repo-standards.yml`.

Nadie la edita a mano. La reemplaza, mediante un PR, la sección «Publicar el verificador central» de `/sync-rules` del hub. Un cambio al verificador se hace en el hub y se publica aquí con ese flujo.

## `VERSION`

Es el commit del hub del que salen los archivos de la copia, y el valor que el workflow pasa al verificador con `--version`. La revisión `skill-version` falla en un repositorio cuya copia de `.claude/skills/repo-standards/VERSION` sea distinta. Este repositorio tiene esa copia, así que su propio `VERSION` y el de `.claude/skills/repo-standards/` deben coincidir.

## Escaneo de secretos

El escaneo central de gitleaks no vive en esta carpeta: su configuración está en [`gitleaks/`](../gitleaks/README.md) y nunca sale del repositorio que llama.

## Comandos

Verificar un repositorio (el de la raíz, en este caso):

```bash
python3 -I repo-standards/verify.py . --version "$(cat repo-standards/VERSION)" \
  --repo-private=false --central-gitleaks=gitleaks --repo-name=.github
```

`--repo-private=false` aplica las reglas de un repositorio público (solo el valor exacto `true` aplica las privadas; sin la opción rige la pública). `--central-gitleaks` y `--repo-name` permiten comprobar que un `.gitleaksignore` o `.gitleaks.toml` del repositorio tenga su archivo de excepciones en `gitleaks/allow/`.
