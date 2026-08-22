# CLAUDE.md — cv-agent

## Autoría de commits: nunca Claude como colaborador

Este repositorio es público y forma parte de una entrega para el Reto IA Banorte. **No
agregues el trailer `Co-Authored-By: Claude...` (ni ninguna variante) a los mensajes de
commit de este proyecto.** El default global de la herramienta lo añade automáticamente;
para este repo queda explícitamente desactivado.

Ya se corrigió cuatro veces porque el trailer volvía a aparecer en sesiones nuevas y
GitHub listaba a "claude" como colaborador en `https://github.com/xoalejo/cv-agent`. La
última vez requirió reescribir el historial (`git filter-branch` + `push --force-with-lease`)
para quitarlo de los commits ya publicados — evita que vuelva a pasar.

Confirma antes de un push forzado, como con cualquier reescritura de historial en un repo
con remoto compartido.
