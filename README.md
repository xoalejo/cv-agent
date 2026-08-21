# CV Agent — Agente conversacional de trayectoria profesional

[![CI](https://github.com/xoalejo/cv-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/xoalejo/cv-agent/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Agente que conversa sobre el perfil profesional de **Oscar Alejo**, expuesto como
endpoint HTTP compatible con el contrato **[Open Responses](https://www.openresponses.org/)**.

Construido para el **Reto IA Banorte**. Este documento explica no solo cómo
funciona, sino **por qué está construido así**: cada decisión relevante viene con
su razón y, cuando aplica, con la alternativa que se descartó.

---

## Índice

- [Qué hace](#qué-hace)
- [Arranque rápido](#arranque-rápido)
- [Arquitectura](#arquitectura)
- [Decisiones técnicas y su porqué](#decisiones-técnicas-y-su-porqué)
- [Seguridad](#seguridad)
- [Verificación](#verificación)
- [Despliegue](#despliegue)
- [Registro en la plataforma](#registro-en-la-plataforma)
- [Limitaciones conocidas](#limitaciones-conocidas)
- [Estructura del proyecto](#estructura-del-proyecto)

---

## Qué hace

Responde preguntas sobre experiencia, habilidades, proyectos, patentes y
formación, en **español o inglés** según el idioma de quien pregunta, manteniendo
la continuidad del hilo de conversación.

```bash
curl -X POST https://<tu-app>.fly.dev/responses \
  -H "Authorization: Bearer $AGENT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"input": "¿En qué empresas ha trabajado con RAG?"}'
```

```json
{
  "id": "resp_...",
  "object": "response",
  "status": "completed",
  "output": [
    {
      "type": "message",
      "role": "assistant",
      "content": [{ "type": "output_text", "text": "Ha trabajado con RAG en…" }]
    }
  ],
  "output_text": "Ha trabajado con RAG en…",
  "usage": { "input_tokens": 3421, "output_tokens": 187, "total_tokens": 3608 }
}
```

---

## Arranque rápido

Requisitos: Python 3.11+ y una clave de la API de OpenAI.

```bash
git clone https://github.com/xoalejo/cv-agent.git
cd cv-agent

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edita .env: OPENAI_API_KEY y AGENT_API_KEY (genera una con el comando de abajo)
python -c "import secrets; print(secrets.token_urlsafe(32))"

uvicorn src.interfaces.http.app:app --reload
```

Probar:

```bash
curl -X POST http://localhost:8000/responses \
  -H "Authorization: Bearer $AGENT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"input": "¿Cuántos años de experiencia tiene?"}'
```

Pruebas y evaluación:

```bash
pip install -e ".[dev]"
pytest                                              # 109 pruebas, sin red
python evals/run_evals.py --base-url http://localhost:8000
```

---

## Arquitectura

Un solo servicio Python con **Clean Architecture**. Las dependencias apuntan
hacia adentro: el dominio no conoce a nadie, la aplicación define puertos, la
infraestructura los implementa y la capa HTTP entrega.

```
 interfaces/http  ──►  application  ──►  domain
     (FastAPI)        (casos de uso,     (entidades +
                        puertos)          políticas)
                            ▲
                            │ implementan los puertos
                     infrastructure
                (OpenAI, perfil, búsqueda)
```

### Flujo de un turno

```
Plataforma ──POST /responses (Bearer)──► interfaces/http
                                              │ auth · rate limit · DTO permisivo
                                              ▼
                                     AnswerProfileQuestion
                                              │ instructions = perfil + guardrails
                                              ▼
                                       OpenAIResponsesEngine
                                        responses.create(store=False)
                                              │
                                   ┌──────────┴───────────┐
                            ¿function_call?          respuesta final
                                   │                       │
                          ejecuta la herramienta            ▼
                          y reinyecta el resultado    redacción de PII
                          en el array de input              │
                                   │                        ▼
                                   └──► reintenta      Response JSON
                                       (máx. 5 vueltas)
```

---

## Decisiones técnicas y su porqué

### 1. La Responses API de OpenAI como motor, sin gateway externo

**Alternativa descartada:** montar el gateway open source
[`open-responses/open-responses`](https://github.com/open-responses/open-responses)
para no reimplementar el protocolo. Su instalador está roto: la empresa detrás
(Julep AI) pivotó a otro producto y los enlaces de quick-start de `u.julep.ai`
redirigen a un sitio distinto. Depender de un proyecto con señales de abandono
para la pieza que maneja la conversación no es defendible cuando el sistema se
audita.

**Alternativa descartada:** reimplementar el spec completo a mano. Habría gastado
el presupuesto de tiempo en *plumbing* de protocolo, que no es lo que el reto
evalúa.

**Decisión:** usar la Responses API de OpenAI como motor. El spec abierto de Open
Responses está modelado sobre ese contrato, así que hablar la forma correcta sale
casi gratis, y el esfuerzo queda donde sí aporta: grounding, herramientas,
guardrails, seguridad y evaluación. Todo el código que toca la conversación es
propio y auditable.

### 2. Clean Architecture, con dos beneficios concretos

No por dogma. Se justifica por dos cosas medibles:

1. **Independencia de proveedor.** El puerto `LLMEngine` deja el adaptador de
   OpenAI sustituible. Es la misma tesis que sostiene a Open Responses —desacoplar
   el agente del proveedor— aplicada al código propio.
2. **Testabilidad sin red.** Con los puertos en dobles, todo el núcleo se prueba
   sin llamar a ningún servicio: **109 pruebas en ~1.4 s, sin gastar un token**.
   Eso es lo que hizo viable tener pruebas y evals reales en el tiempo disponible.

### 3. Contexto completo, no RAG con base vectorial

El perfil son ~1,500 palabras en dos idiomas: **cabe entero en el contexto**. Un
pipeline de RAG con embeddings y base vectorial sobre un corpus de ese tamaño
añade un servicio que operar, una dependencia que mantener y latencia por
consulta, sin mejorar el recall de forma medible. Habría sido acumular tecnología
sin una razón clara.

Para la búsqueda transversal se usa un **índice léxico en memoria** (normalización
sin acentos, coincidencia por términos, cobertura simultánea ES/EN). Queda detrás
del puerto `ProfileSearch`, así que sustituirlo por embeddings el día que el
corpus crezca no toca el caso de uso: la decisión está argumentada *y* es
reversible.

### 4. `store=False`: memoria del hilo sin datos en reposo

Dos conceptos que conviene no confundir:

- **La memoria del hilo** la aporta el historial que llega en `input` en cada
  petición. La plataforma opera en modo "Reproducir transcripción", así que el
  agente ve todos los turnos previos y responde con contexto completo.
- **`store=False`** impide que OpenAI conserve la conversación en sus servidores.
  Por defecto la Responses API persiste, y esa persistencia es la que habilita
  `previous_response_id`.

El resultado es **continuidad conversacional completa con cero conversaciones en
reposo**, ni en el proveedor ni en este servicio. En una prueba para una
institución financiera, poder afirmar que el sistema no almacena las
conversaciones de quien lo prueba es una posición más sólida que cualquier
esquema de sesiones.

El ciclo de herramientas también es stateless: los ítems `function_call` y
`function_call_output` se acumulan en el array de `input` local y se reenvían.

### 5. Herramientas que aportan trazabilidad

| Herramienta | Aporte |
|---|---|
| `search_profile(query)` | **fragmentos con su procedencia** (sección + empresa) |
| `get_experience(company?)` | detalle por empresa |
| `get_projects(name?)` | proyectos propios |
| `get_certifications()` | certificaciones |
| `get_patents()` | patentes IMPI en trámite |
| `get_tech_stack(category?)` | stack por categoría |
| `get_contact_info()` | canales de contacto permitidos |

**`search_profile` es la que carga el peso arquitectónico.** Devuelve cada
fragmento etiquetado con su origen, de modo que una afirmación del agente puede
rastrearse hasta una sección concreta del CV en lugar de emerger difusa del
prompt. Es el mecanismo de grounding y lo que hace la respuesta auditable.

**Se descartó una herramienta que consultara GitHub en vivo.** La justificación
era "traer datos que el CV no tiene", pero quien pregunta por una trayectoria
profesional no necesita el listado de repositorios, y exponerlo publicaría
actividad no curada para este contexto. Quitarla resultó además ser una mejora de
seguridad: **sin herramientas que consuman servicios externos, ningún dato no
confiable entra al contexto del modelo**, lo que elimina de raíz la inyección vía
salida de herramienta en lugar de tener que mitigarla.

### 6. El servidor decide el modelo

La plataforma ofrece un campo "Modelo" opcional que viaja como `model` en el
cuerpo de la petición. **Se ignora deliberadamente.** Aceptarlo dejaría que un
tercero forzara un modelo caro o inexistente contra la cuenta que paga las
llamadas. El modelo se configura por variable de entorno en el servidor.

### 7. El agente habla *de* Oscar, no *como* Oscar

Responde en tercera persona. Un endpoint público que se hace pasar por una
persona real es una decisión que habría que justificar ante quien evalúa; un
asistente que representa un perfil no lo necesita, y deja claro a quien pregunta
que conversa con un sistema.

### 8. Correcciones sobre el CV de origen

Los PDFs en español e inglés traían datos divergentes que habrían producido
**respuestas contradictorias según el idioma de la pregunta**:

| Dato | ES original | EN original | Unificado |
|---|---|---|---|
| Reconocimiento IT Masters | "entre 300 proyectos" | "among 60 projects" | **300** |
| Categoría AppSec del stack | presente | ausente | **presente en ambos** |
| Periodo del proyecto multi-agente | "2026" | "2025 – Present" | **2025 – Presente** |

El perfil vive como estructura de datos única con ambos idiomas en el mismo
objeto, precisamente para que no vuelvan a desincronizarse.

---

## Seguridad

El contexto es una prueba técnica para una institución financiera. Las decisiones
se tomaron con ese criterio.

### Política de divulgación en tres capas

El teléfono personal **no se comparte nunca**. No se implementa como una petición
al modelo, sino como una propiedad del sistema:

1. **El número no existe en los datos.** No hay dato que filtrar, ninguna
   herramienta puede devolverlo y ninguna inyección puede extraerlo de una fuente
   que no lo contiene.
2. **La regla vive en el dominio** (`ALLOWED_CONTACT_KINDS`), no suelta en un
   prompt. El prompt la refuerza, pero no es la única línea de defensa.
3. **Un guarda revisa la salida final** por si el número entró por otra vía —por
   ejemplo, alguien que ya tiene el CV lo pega en el chat y pide confirmarlo.

El número **tampoco se codifica en el detector**: hacerlo publicaría en un
repositorio público exactamente el dato que se protege, y un hash de diez dígitos
es trivial de revertir por fuerza bruta. La detección es por *forma*, con guardas
verificadas contra falsos positivos en expedientes de patente (`MX/a/2024/008296`)
y métricas del CV (17,000 archivos, 140 máquinas, normas como IATF 16949).

**Los PDFs originales del CV no están en este repositorio** (`.gitignore` cubre
`CV/`). Contienen el teléfono, y GitHub indexa permanentemente lo que se sube:
publicarlos contradiría la política que el propio sistema implementa.

### Otros controles

| Control | Implementación |
|---|---|
| **Autenticación** | Bearer obligatorio, comparación en **tiempo constante** (`hmac.compare_digest`) para no filtrar la clave por temporización |
| **Límite de tasa** | Ventana deslizante por credencial o IP; protege el presupuesto del proveedor |
| **Secretos** | Solo por entorno / Fly secrets. `.env` en `.gitignore`, `.env.example` con placeholders |
| **Validación** | Pydantic; estricta en lo propio, tolerante con campos extra del protocolo |
| **CORS** | Cerrado por defecto. Es integración servidor-a-servidor, no un cliente de navegador. Nunca `*` |
| **Errores** | El fallo del proveedor devuelve un 502 genérico; el detalle se queda en logs. *Verificado: un 401 de OpenAI con la clave enmascarada no llega al cliente* |
| **Observabilidad** | Se registran latencia, tokens, herramienta invocada y estado. **Nunca el contenido de las conversaciones ni las credenciales** |
| **Contenedor** | Base slim, build en dos etapas, **usuario sin privilegios** |
| **Instrucciones del cliente** | Se integran **subordinadas** al prompt propio: pueden ajustar tono, nunca las reglas de divulgación |
| **Control de costo** | Tope de 5 vueltas al modelo por turno; evita bucles de herramientas |

---

## Verificación

### Pruebas unitarias e integración — sin red

```bash
pytest -q     # 109 pruebas en ~1.4 s
```

Cubren las políticas de divulgación (incluidos los falsos positivos), la búsqueda
con procedencia, el registro de herramientas, el ciclo completo de conversación
con la guarda de iteraciones, la construcción del prompt y el contrato HTTP con
su seguridad. Ninguna llama a OpenAI: los puertos se sustituyen por dobles.

### Evaluación de comportamiento — contra el endpoint real

```bash
python evals/run_evals.py --base-url http://localhost:8000
python evals/run_evals.py --base-url https://<tu-app>.fly.dev   # gate final
python evals/run_evals.py --category pii --verbose
python evals/run_evals.py --no-judge     # solo comprobaciones deterministas
```

**22 casos dorados** en 8 categorías:

| Categoría | Qué verifica |
|---|---|
| `recall` | Datos correctos del CV, incluida la cifra corregida (300) |
| `grounding` | Preguntas transversales que ejercitan `search_profile` |
| `honestidad` | Admite lo que no está en el CV en lugar de inventar |
| `pii` | El teléfono no aparece ni ante peticiones directas o insistentes |
| `alcance` | Declina salario y opiniones con cortesía |
| `injection` | Resiste intentos de cambiar sus reglas o revelar el prompt |
| `idioma` | Responde en el idioma de la pregunta, con los mismos hechos |
| `continuidad` | Conversaciones de 2–3 turnos con referencias implícitas |

**Sin Ragas ni DeepEval, a propósito.** Montar el framework habría consumido el
presupuesto que necesitaba el agente, y para este alcance no aporta: lo que se
mide son reglas concretas sobre respuestas concretas. Poder explicar exactamente
qué comprueba cada caso vale más que la sofisticación de la herramienta.

Las comprobaciones objetivas —recall, fuga de PII, idioma— se resuelven **sin
modelo**. El juez LLM interviene solo donde una regla no alcanza: si declinó con
naturalidad, si admitió no saber. Los casos multi-turno reenvían el historial
acumulado en cada petición, igual que la plataforma, así que prueban la
continuidad tal como ocurrirá en producción.

El runner marca en rojo los fallos de `pii` e `injection` como bloqueantes.

---

## Despliegue

```bash
fly launch --no-deploy
fly secrets set \
  OPENAI_API_KEY="sk-..." \
  AGENT_API_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
fly deploy

curl https://<tu-app>.fly.dev/health
```

Una máquina siempre encendida (`min_machines_running = 1`): el agente se prueba de
forma interactiva y un arranque en frío a mitad de una demostración se lee como un
servicio caído. Región `qro` (Querétaro) por cercanía.

### Operación

```bash
fly logs                                    # métricas por turno, sin contenido
fly secrets set AGENT_API_KEY="nueva"       # rotar credencial (redespliega solo)
fly status
```

---

## Registro en la plataforma

En **Agentes → Añadir un agente**:

| Campo | Valor |
|---|---|
| **URL base** | `https://<tu-app>.fly.dev` |
| **Clave de API** | el valor de `AGENT_API_KEY` |
| **Modelo** | *vacío* — lo decide el servidor ([decisión 6](#6-el-servidor-decide-el-modelo)) |
| **Estado de la conversación** | Reproducir transcripción |
| **Instrucciones** | *vacío* — el prompt propio es autoritativo |
| **Entrada de imágenes / archivos** | desactivadas (fuera de alcance) |

La plataforma concatena `/responses` a la URL base. El servicio también responde
bajo `/v1`, así que registrar `https://<tu-app>.fly.dev/v1` funciona igual.

---

## Limitaciones conocidas

Se declaran en lugar de presentarse como resueltas.

- **Sin streaming.** El endpoint responde de forma síncrona y **rechaza
  explícitamente** `stream: true` con un 400 en lugar de ignorarlo. Declarar una
  compatibilidad parcial como total sería peor que no tenerla.
- **Límite de tasa por instancia.** El estado vive en el proceso: con varias
  máquinas el límite es por máquina, no global. Suficiente para este alcance;
  hacerlo global requeriría Redis, una dependencia más que operar.
- **La continuidad depende del cliente.** Al ser stateless, un cliente que envíe
  solo el último mensaje sin historial obtendrá respuestas sin continuidad. Es una
  consecuencia deliberada del diseño, no un defecto.
- **Perfil estático.** El CV vive en código y cambia con un despliegue. Para un
  documento que se actualiza cada pocos meses, una base de datos sería una
  frontera más que operar y respaldar sin resolver ningún problema real.
- **Solo texto.** Sin entrada de imágenes ni archivos.

---

## Estructura del proyecto

```
src/
├── domain/                 # Núcleo: sin dependencias externas
│   ├── profile.py          # Entidades del perfil
│   ├── fragment.py         # Fragmento + procedencia (grounding)
│   └── policies.py         # Políticas de divulgación
├── application/            # Casos de uso y puertos
│   ├── ports.py            # LLMEngine, ProfileRepository, ProfileSearch
│   ├── conversation.py     # Ciclo del turno y de herramientas
│   ├── prompt.py           # Instrucciones desde datos + políticas
│   └── tool_registry.py    # Definición y despacho de herramientas
├── infrastructure/         # Adaptadores
│   ├── openai_engine.py    # LLMEngine → Responses API (store=False)
│   ├── profile_data.py     # El CV como datos, sin teléfono
│   └── lexical_search.py   # Búsqueda con procedencia
├── interfaces/http/        # Entrega
│   ├── app.py              # Composition root
│   ├── routes.py           # POST /responses · GET /health
│   ├── schemas.py          # DTOs del protocolo
│   └── security.py         # Auth y límite de tasa
└── config.py

tests/          # 109 pruebas, sin red
evals/          # 22 casos dorados contra el endpoint real
changelog/      # Un fragmento por cambio
```

---

## Licencia

MIT.
