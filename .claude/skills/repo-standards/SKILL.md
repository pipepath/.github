---
name: repo-standards
description: Organización estándar de un repo de Pipepath: README índice, mapa docs/ para personas y para agentes, glosario, README por componente, CI canónica y plantilla de PR; incluye plantillas y el verificador. Usar al crear un repo, al escribir o reorganizar documentación, o cuando el check `standards` falle.
---

# repo-standards: organización estándar de un repo de Pipepath

Un repo de Pipepath se entiende en pocos minutos sin leer código: un README que indexa, un mapa de
`docs/` que separa lo que leen las personas de lo que usan los agentes, un glosario y una CI igual en
todos los repos. El verificador (`verify.py`, en esta carpeta) comprueba la regla; las plantillas
(`templates/`) la cumplen de partida: un repo armado solo con ellas no tiene FAIL.

## Qué se estandariza

### Documentación

- **Archivos obligatorios:** `README.md`, `docs/README.md`, `.github/pull_request_template.md` y
  `.github/workflows/standards.yml`. `docs/glosario.md` es obligatorio desde que el repo tiene dos o más
  documentos para personas.
- **Primera línea:** el README, `docs/README.md` y cada documento para personas empiezan con un H1 y,
  justo después, un párrafo simple que dice qué es y para quién.
- **Largo:** el README avisa en 120 líneas y falla en 240. `docs/README.md` y cada documento para
  personas avisan en 150 y fallan en 300.
- **Mapa `docs/README.md`:** tiene las secciones `## Para personas` y `## Para agentes e implementación`.
  Todo documento para personas, incluido `docs/glosario.md`, aparece enlazado en el mapa. Quedan fuera de
  esa lista `docs/superpowers/` y los README de `.github/`, `.claude/` y carpetas ocultas.
- **README por componente:** cada carpeta de primer nivel con su propio `README.md` (plantilla
  `templates/component-README.md`) cuenta como documento para personas y debe estar en el mapa. No
  cuentan las carpetas `docs/`, `org-rules/`, `logs/`, `knowledge/`, `node_modules/` ni las que
  empiezan con punto.
- **Enlaces:** los enlaces y anclas internos tienen que existir.
- **Diagramas Mermaid:** como máximo 2 por documento y 12 nodos por diagrama. Se cuentan los nodos de
  `flowchart` y `graph` (ids de nodo) y los participantes de `sequenceDiagram`; los otros tipos de
  diagrama no se cuentan por nodos.
- **Sin vocabulario de proceso** en los documentos para personas: no se escribe "task N", "ruling",
  "ledger", "fix round", "controller", ids de agente ni nombres de rama de trabajo (`feat/`, `fix/`,
  `chore/`, `work/`). La revisión no distingue mayúsculas y minúsculas, e ignora código, comentarios
  HTML y destinos de enlaces.

### Integración continua

- **Runner canónico:** todo job usa el `runs-on` canónico (el de `templates/github/workflows/ci.yml`),
  salvo los que figuren en `.github/standards-allow.yml`.
- **Acciones fijadas:** todo `uses:` no local se fija por SHA de 40 hex **y** lleva al final un
  comentario `# versión` (ejemplo: `actions/checkout@<sha> # v7.0.1`). Quedan exentos `./…` y
  `docker://…@sha256:…`.
- **Job `required`:** al menos un archivo de workflow define un job llamado `required`, y su `needs`
  lista todos los demás jobs de ese mismo archivo. No hace falta uno en cada archivo (por ejemplo,
  `standards.yml` no lo tiene). Para que el agregado no falle abierto se acepta solo una de dos formas:
  (a) el job no tiene `if:` (o `success()`), de modo que GitHub lo salta, y el check falla, cuando un
  `needs` falla; o (b) tiene `if: always()` (también `!cancelled()` o `failure()`) **y** un paso cuyo
  `run: |` es exactamente una de las dos formas canónicas: el bloque
  `if [ "${{ contains(needs.*.result, 'failure') || contains(needs.*.result, 'cancelled') || contains(needs.*.result, 'skipped') }}" = "true" ]; then … exit 1; fi`
  (el de `templates/github/workflows/ci.yml`), o la de spawn-control (una variable de entorno
  `${{ needs.<job>.result }}` por cada `needs`, un `ok=false`, el `if` de evento y de `= "success"` que
  pone `ok=true`, y un `exit 1` final si `ok` no es `true`). Un `echo ok`, un chequeo solo de `failure`
  (una cancelación se cuela), un `|| true` o cualquier otra forma es FAIL. El paso y el job no pueden
  tener `continue-on-error`, `shell:`, `working-directory`, `timeout-minutes: 0`, `strategy`, ni un `if:`
  que no sea los anteriores.
- **gitleaks:** queda cubierto de una de dos maneras. (1) **Estructural:** `.github/workflows/standards.yml`
  llama al workflow central, que corre gitleaks con la imagen fijada por digest sobre el historial
  completo del repo que llama (`fetch-depth: 0`, `persist-credentials: false`) con código que el repo no
  puede editar. Ese archivo debe disparar en `pull_request` (sin filtros: ni `paths`, `paths-ignore`,
  `branches`, `branches-ignore` ni `types`) y en `push` a `main` (sin filtros salvo `branches: [main]`),
  y llamar al workflow central fijado por SHA de 40 hex con comentario de versión, sin `if:` ni
  `continue-on-error`. (2) **Job local** con exactamente esta forma (una lista de pasos con solo
  `actions/checkout` y el paso del escaneo, y el escaneo en **una sola línea**): 
  `docker run --rm -v "$PWD:/repo" ghcr.io/gitleaks/gitleaks:vX.Y.Z@sha256:<64 hex> git /repo [--redact] [--verbose] [--config <ruta>]`.
  El job necesita un checkout con `fetch-depth: 0` antes, y ni él ni el workflow ni el paso pueden usar
  `shell:` o `defaults.run.shell`, `continue-on-error`, `timeout-minutes: 0`, `working-directory`, `env:`
  (ni `DOCKER_*`, `BASH_ENV`, `PATH`, `LD_*` en el `env:` del workflow), claves duplicadas, construcciones
  YAML no modeladas (flow sequences o mappings salvo `with: { fetch-depth: 0 }`, anclas, etiquetas), un
  `if:` en el job o en el paso, ni documentos múltiples. El workflow donde vive debe tener los mismos
  disparadores que `standards.yml`. Es una lista cerrada, no una lista de trucos prohibidos.
- **Excepciones de gitleaks:** el escaneo central **ignora** el `.gitleaks.toml` del repo, su
  `.gitleaksignore` y los comentarios `gitleaks:allow` en línea; el verificador no lee ningún
  `.gitleaks.toml`. La configuración sale solo de `pipepath/.github`: `gitleaks/base.toml` (reglas por
  defecto) más, si existe, `gitleaks/allow/<repo>.toml`. Una excepción para un repo se pide con un PR a
  `pipepath/.github` que agregue una entrada `[[allowlists]]` en ese archivo, con `paths` anclados
  (`^…$`) **y** `commits`, `regexes` o `targetRules`, y un comentario con el motivo en cada entrada. El
  CI de ese repo carga cada archivo contra la imagen fijada, así que uno malformado falla el PR. El
  `.gitleaks.toml` propio de un repo solo afecta a su job local de gitleaks, si lo tiene.
- **Check central `standards`:** corre desde su propio workflow, `.github/workflows/standards.yml`, que
  llama al workflow reutilizable de `pipepath/.github` y no le pasa `secrets:` (tampoco `secrets: inherit`;
  es FAIL `standards-workflow`). Como `needs` no puede apuntar a un job de otro
  archivo de workflow, `standards` se marca como check requerido **junto a** `required` en la protección
  de rama; no va dentro de `required.needs`.
- **Estructura del workflow:** solo cuentan los archivos `.github/workflows/*.yml` y `*.yaml` de primer
  nivel (los demás GitHub no los ejecuta). Un job repetido, una clave repetida (en el archivo, en un job o
  en un paso), un `needs` a sí mismo, a un job que no existe o con ciclo, y un archivo con varios
  documentos YAML son FAIL: GitHub y este analizador podrían leerlos distinto, o GitHub rechazaría el
  workflow.
- **Lo que el analizador no modela** (job en flow mapping, `runs-on` como lista, anclas o alias, matrices,
  claves entre comillas, un archivo ilegible o con `jobs:` sin jobs reconocibles) produce **FAIL**, nunca
  WARN: el check bloquea, así que ante la duda falla. Un job que no se puede modelar solo se acepta si su
  clave exacta `<archivo>/<job>` figura en `.github/standards-allow.yml` con motivo; reescribirlo en
  estilo de bloque es la salida preferida.

### Plantilla de PR

`.github/pull_request_template.md` con las secciones `## Qué cambia`, `## Cómo se probó` y `## Spec`.

## Cómo aplicarlo a un repo

1. Copia las plantillas: `templates/README.md` a `README.md`; `templates/docs/README.md` y
   `templates/docs/glosario.md` a `docs/`; `templates/github/pull_request_template.md` a `.github/`;
   `templates/github/workflows/standards.yml` y `templates/github/workflows/ci.yml` a `.github/workflows/`. Para cada componente con README
   propio, usa `templates/component-README.md`.
2. Rellena todos los `<…>`. Cada comando que escribas se prueba contra el código antes de dejarlo en el
   documento; un comando que no corre es peor que ninguno.
3. Lista en `docs/README.md` cada documento para personas, glosario y READMEs de componente incluidos.
4. En `ci.yml`, reemplaza el job `test` de relleno (su comando está marcado `PLACEHOLDER`) por los jobs
   que correspondan y agrégalos a `required.needs`. Conserva el runner canónico, las acciones fijadas
   por SHA con su comentario de versión, el job `gitleaks` y el job `required`.
5. El SHA del workflow central en `standards.yml` lo fija `/sync-repos`; no lo edites a mano.
6. Verifica (siguiente sección) y corrige hasta que no haya FAIL.

`templates/central/repo-standards.yml` es el workflow reutilizable que vive en `pipepath/.github` (un repo
público); los repos no lo copian. Hace checkout del repo que llama y de `pipepath/.github` en el commit del
workflow llamado (`job.workflow_sha`), y ejecuta el verificador con la `VERSION` de esa copia. Ambos jobs
corren Python con `-I`. El job `gitleaks` nunca lee la configuración del repo que llama: compone con `cat`
`gitleaks/base.toml` y, si existe, `gitleaks/allow/<nombre>.toml` (el nombre es `github.repository` sin
`pipepath/`, pasado por `env:`, validado con `^[A-Za-z0-9_.-]+$` y distinto de `.` y `..`; otro dueño u otro
nombre recibe solo la base) en `$RUNNER_TEMP`, y la monta de solo lectura en la imagen fijada (`--config`).
Antes del escaneo neutraliza los otros controles que controla el repo (comprobado con la imagen fijada):
gitleaks carga solo `<repo>/.gitleaksignore` aunque se pase `--gitleaks-ignore-path`, así que se borra de la
copia de trabajo (el escaneo lee el historial) y la opción apunta a un archivo vacío central; un
`.gitattributes` con `* -diff` oculta los parches de `git log -p`, así que `.git/info/attributes` fuerza
`* diff` (a costa de más tiempo de escaneo y posibles hallazgos extra en binarios: falla cerrado); los
comentarios `gitleaks:allow` se ignoran (`--ignore-gitleaks-allow`); el historial es explícito
(`--log-opts="--full-history --all"`). `docker` corre con `env -i` (solo `PATH` y `HOME`) y `--config` gana
sobre `GITLEAKS_CONFIG`. El workflow no tiene `inputs`: el repo que llama es el commit del evento y el
central está fijado a `job.workflow_sha`. En un runner en contenedor con el demonio Docker del host, los
montajes pueden no existir en el host: el escaneo falla cerrado, no abierto. El verificador solo lee archivos
del repo que llama: un test impide `subprocess`, `exec`, `eval`, importación dinámica y similares en
`verify.py` y `standards/`.

**Repos públicos.** Un repo público nunca debe llegar a los runners propios. El runner canónico cae a los
hospedados solo mientras `PIPEPATH_RUNNER` no está definida (infra lo garantiza para los públicos); la
opción `verify.py --public` lo fija: es FAIL `runs-on` todo job cuyo `runs-on` no sea exactamente la
expresión canónica (un `self-hosted`, una etiqueta `pipepath-`, un runner hospedado literal o una matriz),
incluidos los de `.github/standards-allow.yml` y los que no se pueden modelar. El workflow central la
agrega salvo que `github.event.repository.private` sea exactamente `true` (por `env:`; vacío cuenta como
público). Sin la opción el comportamiento no cambia.

## Cómo verificar

```bash
python3 .claude/skills/repo-standards/verify.py . --format text
```

Códigos de salida: 0 sin FAIL, 1 con algún FAIL, 2 error de uso (por ejemplo, la ruta no es una
carpeta). Los WARN no bloquean, pero conviene revisarlos. Un documento que no se puede leer (no es UTF-8,
es una carpeta o un enlace roto) produce un WARN `unreadable` una sola vez, y las demás revisiones lo
omiten. Un workflow ilegible es FAIL (`workflow-parse`).

### Versión del skill

`.claude/skills/repo-standards/VERSION` lo escriben `/sync-rules` y `/sync-repos`; nunca se edita a
mano. El check central `standards` pasa su propia `VERSION` con `--version`, y la revisión
`skill-version` falla si la copia del repo es distinta (o no existe): la solución es correr
`/sync-repos`. Sin `--version`, esa revisión no corre.

## Excepciones

Un job puede usar otro `runs-on`, o ser uno que el analizador no sabe modelar, si figura en
`.github/standards-allow.yml`, una línea por job con la forma `<archivo>/<job>: motivo`. La clave debe
coincidir exacta (archivo y job completos, no un prefijo) y la línea sin motivo no cuenta. La excepción
no exime de `gitleaks`, `required` ni de las acciones fijadas.

```yaml
# .github/standards-allow.yml
ci.yml/build-macos: necesita un runner macOS para compilar la app
```

## Modelo de amenaza y límites conocidos

El verificador es un **check de conformidad**: detecta desvíos y errores de buena fe de miembros y
agentes de confianza. No es una frontera de seguridad frente a un adversario: la organización no tiene
protección de rama (GitHub Free, repos privados), así que quien escribe en un repo puede borrar el
workflow. Por eso lo que importa se hace estructural (el workflow central corre gitleaks por su cuenta) y
lo que el analizador acepta es una lista cerrada de formas canónicas, no una lista de trucos prohibidos.

Límites conocidos, aceptados bajo ese modelo:

- El analizador lee líneas, no YAML completo: otras construcciones exóticas (por ejemplo, un `run:` en
  varias líneas de texto plano continuado) se rechazan o se ignoran según el caso; no se persiguen más
  variantes.
- No comprueba que el SHA del workflow central en `standards.yml` sea el más reciente: eso lo mantiene
  `/sync-repos`. Solo exige que sea un SHA de 40 hex con comentario de versión y del workflow correcto.
- No juzga que los jobs reales (`test`, etc.) prueben algo, ni que `required` agregue jobs de otros
  archivos de workflow.
- Un job que otro `needs` que se salta también se salta; el chequeo `skipped` del agregado lo cubre, pero
  el verificador no recorre el grafo de condiciones.
- La excepción de `standards-allow.yml` solo exime del `runs-on` y de lo que el analizador no modela;
  no exime de gitleaks, de `required` ni de las acciones fijadas.

## Qué no hacer

- No edites esta copia del skill en un repo: `/sync-repos` la reemplaza. Un cambio al estándar se hace
  en el hub y se distribuye.
- No metas vocabulario de proceso (tareas, rondas de revisión, nombres de rama, ids de agente) en los
  documentos para personas; eso vive en los planes y en la bitácora.
- No dejes un documento para personas fuera del mapa `docs/README.md`.
- No fijes una acción por etiqueta (`@v4`) ni omitas el comentario de versión.
- No agregues una excepción sin motivo escrito.
