# CLAUDE.md — cv-agent

## Autoría de commits: nunca Claude como colaborador

Este repositorio es público y forma parte de una entrega para el Reto IA Banorte.

**Todo mensaje de commit termina con el cuerpo (motivación / qué cambia); no lleva
ninguna línea de firma, trailer o footer después de eso.** En particular, nunca
`Co-Authored-By: Claude...` ni ninguna variante que nombre a Claude o Anthropic. El
default global de la herramienta añade ese trailer automáticamente al terminar el
mensaje; para este repo esa plantilla no aplica — el mensaje simplemente se cierra
sin agregar nada más.

**Por qué una regla prescriptiva y no solo una prohibición:** decir "no agregues X" deja
un hueco que compite con el comportamiento por defecto de la herramienta, y ese hueco se
volvió a llenar solo cuatro veces en sesiones nuevas — GitHub llegó a listar a "claude"
como colaborador en `https://github.com/xoalejo/cv-agent`. La última vez requirió
reescribir el historial (`git filter-branch` + `push --force-with-lease`) para quitarlo de
los commits ya publicados. Definir explícitamente dónde termina el mensaje, en vez de solo
prohibir la línea que no debe llevar, cierra el hueco en vez de dejarlo abierto para que
alguna sesión futura vuelva a llenarlo por default.

Confirma antes de un push forzado, como con cualquier reescritura de historial en un repo
con remoto compartido.
