# Glosario

Los términos que usan los documentos de este repo, en orden alfabético.

| Término | Qué significa |
|---|---|
| Allowlist | Entrada de `gitleaks/allow/<repo>.toml` que silencia un falso positivo confirmado de un repositorio |
| Check central | El workflow reutilizable `repo-standards` de este repositorio, que llaman los demás repositorios |
| gitleaks | Herramienta que busca secretos en el historial de un repositorio |
| SHA fijado | Referencia a un commit de 40 caracteres, que impide que el código llamado cambie sin revisión |
| Verificador | La copia de `verify.py` y `standards/` que comprueba que un repositorio cumple el estándar |
| `VERSION` | El commit del hub del que sale la copia del verificador |
