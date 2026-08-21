# El perfil pasa a un solo idioma canónico

**Rama:** `main`
**Fecha:** 2026-08-21

## Motivación

El perfil se almacenaba con cada campo duplicado en español e inglés. Esa
estructura obliga a aplicar cada actualización del CV dos veces, y una omisión
produce respuestas distintas según el idioma en que se pregunte: exactamente el
problema que se quería evitar.

## Cambio

El perfil se almacena **solo en español**, el idioma original del CV. La respuesta
en inglés se resuelve traduciendo en el momento.

- `LocalizedText` desaparece del dominio; los campos del perfil son cadenas.
- El prompt fija qué se conserva sin traducir: nombres de empresas e
  instituciones, números de expediente, normas y los títulos oficiales de las
  patentes, registrados en español ante el IMPI.
- Las herramientas pierden el parámetro `language`: devuelven el contenido
  canónico y el modelo traduce al redactar la respuesta.
- El índice de búsqueda queda en español, y el prompt instruye al modelo a
  formular la consulta en ese idioma aunque converse en otro.

El contenido se migró extrayéndolo programáticamente de la estructura anterior,
no transcribiéndolo a mano: 3 experiencias, 19 logros, 9 categorías de stack, 4
certificaciones, 3 patentes, 1 proyecto y 4 reconocimientos, verificados tras la
migración.

## Efecto medido

El prompt pasa de **~5,500 a ~3,700 tokens**, un 33% menos. El perfil viaja
completo en cada turno, así que el ahorro se repite durante toda la conversación.

## Corrección en la búsqueda

Al fijar la premisa del corpus en español apareció un defecto previo: la
coincidencia por subcadena operaba en cualquier posición de la palabra, de modo
que `"files"` casaba con `"per**files**"` y devolvía fragmentos sin relación con
la consulta. La coincidencia se ancla ahora al inicio de palabra, que era la
intención original —`"kube"` → `"kubernetes"`— sin el ruido.

## Archivos

- `src/domain/profile.py`, `src/domain/policies.py`
- `src/infrastructure/profile_data.py` (regenerado), `src/infrastructure/lexical_search.py`
- `src/application/prompt.py`, `src/application/tool_registry.py`, `src/application/ports.py`
- `tests/unit/` — las pruebas que verificaban la estructura bilingüe se
  reescribieron para verificar las propiedades del nuevo diseño.

117 pruebas en verde.
