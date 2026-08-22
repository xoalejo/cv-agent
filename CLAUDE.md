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

## Convención de asunto de commits

**Formato:** `tipo(scope): asunto`, igual que en los proyectos `bank_agent` y `NXC` del
mismo autor — se adopta la misma convención para que los tres sean consistentes.

**Tipos:** `feat`, `fix`, `refactor`, `chore`, `docs`, `perf` (latencia/eficiencia medible;
si no hay medición, es `refactor`). `build`/`ci`/`test` solo si surge necesidad real.

**Scopes vigentes de este proyecto:** `repo` (cross-cutting: CI, licencia, formato general),
`domain`, `application`, `infrastructure`, `interfaces`, `profile` (contenido del CV),
`prompt`, `streaming`, `a2a`, `api` (rutas/versionado), `evals`, `deploy`, `ci`, `config`.
No inventar un scope si uno existente ya cubre el cambio.

**Compuesto con `+`** si un commit toca dos áreas de forma genuina:
`fix(evals): rúbrica de pii daba rojo falso + feat(deploy): agrega Hugging Face Spaces`.
No forzar un solo commit por PR a costa de mezclar tipos distintos en un asunto que no
los distinga.

**Asunto:** minúscula tras los dos puntos salvo siglas y nombres propios (CV, README,
CI, SSE, CORS, A2A, GPT-5.6, Vercel, GitHub, OpenAI...), sin punto final, ≤110 caracteres
por fragmento (≤130 si es compuesto). Describe síntoma + ubicación + impacto para `fix`,
no la solución — así se encuentra con `git log --grep` cuando algo reincide.

**Cuerpo:** motivación y causa raíz, en el mismo nivel de detalle que ya tienen los
commits existentes del repo — no se resume, se explica.

Aplica a todo commit nuevo en este repositorio, no solo a la reestructuración retroactiva
que ya se hizo sobre el historial existente.
