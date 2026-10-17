# pipepath/.github

Repositorio central de la organización `pipepath`: aloja el check reutilizable `repo-standards` que llaman todos los repositorios de la organización, para quien mantiene o incorpora repositorios.

## Qué es

Es el repositorio `.github` de la organización. Guarda un workflow reutilizable (`.github/workflows/repo-standards.yml`) y la copia del verificador que ese workflow ejecuta (`repo-standards/`). Cada repositorio de Pipepath lo llama desde su propio `.github/workflows/standards.yml`.

Es un repositorio público: no contiene secretos ni datos de infraestructura privada, y los repositorios privados se mencionan solo por nombre.

## Por qué existe

El estándar de organización de repositorios (README índice, mapa de `docs/`, CI canónica, plantilla de PR) se comprueba igual en todas partes. Si cada repositorio llevara su propio verificador, un cambio en el estándar tendría que copiarse a mano. Con un workflow central fijado por SHA, el código que comprueba no lo puede editar el repositorio comprobado, y el escaneo de secretos corre aunque el repositorio quite su propio job.

## Cómo funciona en 30 segundos

- Un repositorio llama al workflow central, fijado por SHA de 40 caracteres.
- El job `verify` ejecuta el verificador de `repo-standards/` sobre el repositorio que llama.
- El job `gitleaks` escanea todo el historial del repositorio que llama con una configuración central.
- Este repositorio se llama a sí mismo con `.github/workflows/standards.yml` y su CI (`.github/workflows/ci.yml`) corre el verificador y gitleaks sobre sí mismo.
- Como es el repositorio `.github` de la organización, su `.github/pull_request_template.md` es también la plantilla de PR por defecto de GitHub para los repositorios de la organización que no tienen una propia.

## Estado

- Existe: el workflow central, la copia del verificador y la conformidad de este repositorio con el estándar.
- En construcción: el despliegue a los demás repositorios de la organización. Hasta que cada uno llame al workflow, el check no cubre toda la organización.
- Plan de esta etapa: [plan de estándares centrales](docs/superpowers/plans/2026-10-17-central-standards.md).

## Qué leer

- [Mapa de la documentación](docs/README.md)
- [README del verificador](repo-standards/README.md): qué es la copia, cómo se actualiza y qué significa `VERSION`.

## Cómo empezar

Comprobar este repositorio contra el estándar, desde la raíz (necesita Python 3.11 o superior):

```bash
python3 -I repo-standards/verify.py . --version "$(cat repo-standards/VERSION)"
```

No debe imprimir ningún `FAIL`. Los mismos comandos corren en CI.
