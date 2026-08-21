# Núcleo del agente de CV conversacional

**Rama:** `main` (scaffold inicial del proyecto)
**Fecha:** 2026-08-21
**Hito:** 1 y 2 del plan, núcleo conversando + herramientas y guardrails

## Motivación

El Reto IA Banorte pide diseñar, construir y desplegar un agente conversacional
que represente una trayectoria profesional, expuesto como endpoint público
compatible con **Open Responses**. Lo que se evalúa es el criterio de AI
engineering: integración del modelo, contexto y herramientas; despliegue y
operación; y verificación de que responda de forma coherente y confiable.

## Decisiones de arquitectura

**Sin gateway externo.** La opción inicial era montar `open-responses/open-responses`
para no reimplementar el protocolo. Se descartó: su instalador está roto porque la
empresa detrás (Julep AI) pivotó a otro producto y los enlaces de `u.julep.ai`
redirigen a `memory.store`. Depender de un proyecto con señales de abandono para
la pieza que maneja la conversación no es defendible en una prueba para un banco.

**La Responses API de OpenAI como motor.** El spec abierto de Open Responses está
modelado sobre ese contrato, así que hablar la forma correcta sale casi gratis y
el esfuerzo queda donde el reto sí evalúa: grounding, herramientas, guardrails,
seguridad y evaluación.

**Clean Architecture con dos beneficios concretos**, no por dogma:
1. El puerto `LLMEngine` deja el proveedor sustituible, la misma tesis que
   sostiene a Open Responses, aplicada al código propio.
2. Con los puertos en dobles, todo el núcleo se prueba sin red: 109 pruebas
   corren en 1.4 s sin gastar una sola llamada al proveedor.

**`store=False` en cada llamada.** La Responses API persiste conversaciones del
lado del proveedor por defecto, y esa persistencia es la que habilita
`previous_response_id`. Aquí el hilo se reconstruye enviando los ítems en cada
petición: continuidad completa con cero conversaciones en reposo fuera del
proceso.

**Búsqueda léxica, no vectorial.** El perfil son ~1,500 palabras en dos idiomas.
Un índice vectorial añadiría un servicio que operar y latencia por consulta sin
mejorar el recall de forma medible. Queda detrás del puerto `ProfileSearch`, así
que sustituirlo por embeddings no tocaría el caso de uso.

## Política de divulgación en tres capas

El teléfono personal no se comparte nunca. Se implementa como propiedad del
sistema, no como esperanza sobre el modelo:

1. El número **no existe** en los datos del perfil, no hay dato que filtrar.
2. `ALLOWED_CONTACT_KINDS` restringe los canales publicables en el dominio.
3. `redact_contact_data` revisa la salida final por si el número entró por otra
   vía (por ejemplo, alguien que ya tiene el CV lo pega y pide confirmarlo).

El número tampoco se codifica en el detector: hacerlo publicaría en un repositorio
público exactamente el dato que se protege. La detección es por *forma*, con
guardas verificadas contra falsos positivos en expedientes de patente
(`MX/a/2024/008296`) y métricas del CV (17,000 archivos, 140 máquinas).

## Modelo de datos bilingüe

El perfil se estructura con ambos idiomas en el mismo objeto (`LocalizedText`) en
lugar de mantener dos documentos paralelos. Una actualización se aplica una sola
vez y el agente no puede dar respuestas distintas según el idioma de la pregunta.

## Archivos

- `src/domain/`, entidades (`profile.py`), fragmentos con procedencia
  (`fragment.py`) y políticas de divulgación (`policies.py`).
- `src/application/`, puertos (`ports.py`), caso de uso con el ciclo de
  herramientas (`conversation.py`), construcción del prompt (`prompt.py`) y
  registro de herramientas (`tool_registry.py`).
- `src/infrastructure/`, adaptador de OpenAI (`openai_engine.py`), perfil como
  datos (`profile_data.py`) y búsqueda léxica (`lexical_search.py`).
- `src/interfaces/http/`, DTOs del protocolo, seguridad, rutas y composition root.
- `tests/`, 109 pruebas, todas sin red.

## Estado

Hitos 1 y 2 cubiertos a nivel de código y pruebas. Pendiente: verificación contra
la API real de OpenAI, despliegue en Fly.io, suite de evals, README y publicación.
