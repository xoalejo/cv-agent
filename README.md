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
pytest                                              # 117 pruebas, sin red
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

Se evaluó montar un gateway open source que ya implementara el protocolo. La
opción más conocida presenta un instalador roto y sin mantenimiento reciente:
delegar en una dependencia sin soporte activo la pieza que gestiona la
conversación no es defendible en un sistema que se audita.

La alternativa opuesta —reimplementar el spec completo a mano— habría consumido
el tiempo disponible en construir protocolo, que no es donde está el valor de
este trabajo.

**Decisión:** usar la Responses API de OpenAI como motor. El spec abierto de Open
Responses está modelado sobre ese contrato, así que hablar la forma correcta sale
casi gratis, y el esfuerzo queda donde sí aporta: grounding, herramientas,
guardrails, seguridad y evaluación. Todo el código que gestiona la conversación es
propio y auditable.

### 2. Clean Architecture, con dos beneficios concretos

No por dogma. Se justifica por dos cosas medibles:

1. **Independencia de proveedor.** El puerto `LLMEngine` deja el adaptador de
   OpenAI sustituible. Es la misma tesis que sostiene a Open Responses —desacoplar
   el agente del proveedor— aplicada al código propio.
2. **Testabilidad sin red.** Con los puertos en dobles, todo el núcleo se prueba
   sin llamar a ningún servicio: **117 pruebas en ~1.3 s, sin gastar un token**.
   Eso es lo que hizo viable tener pruebas y evals reales en el tiempo disponible.

### 3. Contexto completo, no RAG con base vectorial

El perfil son ~1,500 palabras: **cabe entero en el contexto**. Un
pipeline de RAG con embeddings y base vectorial sobre un corpus de ese tamaño
añade un servicio que operar, una dependencia que mantener y latencia por
consulta, sin mejorar el recall de forma medible. Habría sido acumular tecnología
sin una razón clara.

Para la búsqueda transversal se usa un **índice léxico en memoria**: normalización
sin acentos y coincidencia por términos, con los prefijos anclados a inicio de
palabra para no arrastrar falsos positivos. Queda detrás
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

**Todas las herramientas leen del perfil; ninguna consulta servicios externos.**
Esa restricción es deliberada y tiene una consecuencia de seguridad directa:
**ningún dato no confiable entra al contexto del modelo**, lo que elimina de raíz
la inyección de prompt vía salida de herramienta en lugar de obligar a mitigarla.

### 6. El servidor decide el modelo

La plataforma ofrece un campo "Modelo" opcional que viaja como `model` en el
cuerpo de la petición. **Se ignora deliberadamente.** Aceptarlo dejaría que un
tercero forzara un modelo caro o inexistente contra la cuenta que paga las
llamadas. El modelo se configura por variable de entorno en el servidor.

### 7. El agente habla *de* Oscar, no *como* Oscar

Responde en tercera persona. Un endpoint público que simula ser una persona real
plantea un problema de transparencia que un asistente representando un perfil no
tiene, y deja claro a quien pregunta que conversa con un sistema.

### 8. Un solo idioma canónico, traducción en el momento

El perfil se almacena **solo en español**, el idioma original del CV. Cuando la
pregunta llega en inglés, el agente traduce al responder en lugar de leer de una
segunda copia del contenido.

La alternativa —mantener ambas versiones en los datos— obliga a aplicar cada
actualización dos veces, y una omisión produce respuestas distintas según el
idioma en que se pregunte. Con una sola versión esa clase de error no existe.

Tiene además un efecto medible: el prompt pasó de ~5,500 a ~3,700 tokens, **un
33% menos en cada llamada**. El perfil viaja completo en cada turno, así que ese
ahorro se repite en toda la conversación.

Dos consecuencias que el diseño asume explícitamente:

- **La traducción es generada, no curada.** El prompt fija qué debe conservarse
  sin traducir: nombres de empresas e instituciones, números de expediente,
  normas y los títulos oficiales de las patentes, registrados en español.
- **El índice de búsqueda está en español.** Una consulta con vocabulario solo en
  inglés recupera menos, así que el prompt instruye al modelo a formular la
  consulta en español aunque converse en otro idioma. Traducir un término de
  búsqueda es trivial para el modelo; mantener un corpus duplicado no lo es.

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

**Los documentos fuente del CV no forman parte del repositorio** (`.gitignore`
cubre `CV/`). Incluyen datos de contacto que el agente no divulga, y un
repositorio público queda indexado de forma permanente: publicarlos
contradiría la política que el propio sistema implementa.

### Límites de tasa: tres capas distintas

Un agente que llama a una API de pago tiene tres frentes de límite, y confundirlos
lleva a presentar un problema transitorio como una avería.

**1. Entrada — quién nos llama.** Ventana deslizante en memoria, **60 peticiones
por minuto** por credencial o IP. La protección real del endpoint es la
credencial; este límite es defensa secundaria contra una clave filtrada o un
cliente en bucle. Por eso no se aprieta más: la propia suite de evaluación
consume ~26 peticiones seguidas y varias personas pueden estar probando el agente
con la misma clave a la vez. Un límite que bloquea el uso legítimo no aporta
seguridad y degrada el servicio.

**2. Salida — los límites de OpenAI.** El proveedor aplica cuotas de peticiones
por minuto (RPM) y de **tokens por minuto (TPM)**. Como cada turno envía el perfil
completo —del orden de 4-5k tokens de entrada—, **el límite que se alcanza primero
es el de tokens, no el de peticiones**. El SDK reintenta con espera exponencial
(`max_retries=3`) y absorbe los picos breves; si la cuota está saturada de verdad,
el error se traduce en **HTTP 429 con `Retry-After`**, no en un 502. La distinción
importa: un 502 dice "estoy roto" y un 429 dice "espera un momento".

**3. Errores de configuración.** Una credencial inválida o un modelo inexistente
devuelven **503**, no 429 ni 502: reintentar no lo arregla, hay que corregir la
configuración. Tres causas distintas, tres códigos distintos.

En los tres casos el detalle se queda en los logs. Un 429 de OpenAI que menciona
la organización y los TPM de la cuenta nunca llega al cliente — *verificado con
pruebas*.

### Otros controles

| Control | Implementación |
|---|---|
| **Autenticación** | Bearer obligatorio, comparación en **tiempo constante** (`hmac.compare_digest`) para no filtrar la clave por temporización |
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
pytest -q     # 117 pruebas en ~1.3 s
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
| `recall` | Datos correctos del CV: empresas, fechas, formación, patentes |
| `grounding` | Preguntas transversales que ejercitan `search_profile` |
| `honestidad` | Admite lo que no está en el CV en lugar de inventar |
| `pii` | El teléfono no aparece ni ante peticiones directas o insistentes |
| `alcance` | Declina salario y opiniones con cortesía |
| `injection` | Resiste intentos de cambiar sus reglas o revelar el prompt |
| `idioma` | Responde en el idioma de la pregunta, con los mismos hechos |
| `continuidad` | Conversaciones de 2–3 turnos con referencias implícitas |

**Sin Ragas ni DeepEval, a propósito.** Para este alcance no aportan: lo que se
mide son reglas concretas sobre respuestas concretas, y un runner propio permite
explicar exactamente qué comprueba cada caso y por qué. La sofisticación del
framework no compensa esa pérdida de claridad cuando el conjunto de criterios
cabe en un archivo legible.

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
- **Sin control de gasto por tokens.** Se limitan las peticiones, no los tokens
  consumidos. Un cliente autenticado que envíe historiales muy largos gastaría
  más por petición que uno normal. Está acotado por el tope de 200 elementos de
  historial y por el límite de 5 vueltas de herramientas, pero no hay un
  presupuesto de tokens explícito. Para producción real convendría añadirlo, junto
  con alertas de gasto en el panel del proveedor.
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

tests/          # 117 pruebas, sin red
evals/          # 22 casos dorados contra el endpoint real
changelog/      # Un fragmento por cambio
```

---

## Licencia

MIT.
