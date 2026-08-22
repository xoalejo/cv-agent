# Registro del agente en la plataforma

Configuración exacta con la que el agente queda registrado, para poder repetirlo
desde cero sin reconstruir el razonamiento.

Formulario: **Reto IA → Agentes → Añadir un agente**.

---

## Valores del formulario

| Campo | Valor | Por qué |
|---|---|---|
| **Importar desde tarjeta** | `https://cv-agent-amber.vercel.app` | Rellena nombre, descripción y capacidades. La URL base hay que escribirla a mano (ver [limitación](#la-importación-no-rellena-la-url-base)) |
| **Nombre** | `Agente de CV de Oscar Alejo` | Lo importa la tarjeta |
| **Avatar** | 💼 | Opcional |
| **Descripción** | La importa la tarjeta | Se genera desde el perfil, no se teclea |
| **URL base** | `https://cv-agent-amber.vercel.app/v1` | **Con `/v1`.** Es la ruta versionada: designa el contrato al que el servicio se compromete |
| **Clave de API** | Valor de `AGENT_API_KEY` | Viaja como `Authorization: Bearer`. La plataforma la almacena cifrada |
| **Modelo** | *vacío* | El servidor decide el modelo; aceptar el del cliente permitiría forzar uno caro o inexistente |
| **Estado de la conversación** | `Reproducir transcripción (sin estado)` | **Obligatorio.** El servicio es stateless: la continuidad llega en el `input` de cada petición. Con `previous_response_id` el agente perdería el hilo |
| **Entrega de archivos** | `URL de capacidad` | Irrelevante: la entrada de archivos está desactivada |
| **Instrucciones** | *vacío* | El system prompt propio ya es completo y autoritativo. Lo que se ponga aquí entra subordinado y solo puede introducir conflicto |
| **Extra request parameters** | *vacío* | El ejemplo que sugiere la plataforma (`{"temperature": 0.7}`) **fallaría**: GPT-5.6 rechaza `temperature` con un 400. El servicio ignora los parámetros extra, así que no rompe nada, pero no aporta |
| **Entrada de imágenes** | Apagado | Multimodal fuera de alcance |
| **Entrada de archivos** | Apagado | Íd. |
| **Activado** | Encendido | |

### Prompt suggestions

Una por línea. Elegidas para cubrir el rango real del agente: búsqueda
transversal, dato distintivo, impacto medible y bilingüismo.

```
¿En qué empresas ha trabajado con RAG?
¿Qué experiencia tiene en el sector financiero?
Cuéntame de sus patentes ante el IMPI
¿Qué logró en Arbomex y qué impacto tuvo en el negocio?
What is his experience building AI agents?
```

---

## Dónde está cada secreto

La `AGENT_API_KEY` vive en tres sitios y deben coincidir:

| Lugar | Para qué |
|---|---|
| `.env` local | Desarrollo y ejecución de evals |
| Variables de entorno de Vercel (Production) | El servicio desplegado |
| Campo "Clave de API" del formulario | Lo que la plataforma envía |

Copiarla sin mostrarla en pantalla:

```bash
grep '^AGENT_API_KEY=' .env | cut -d= -f2 | tr -d '\n' | pbcopy
```

Generar una nueva:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Rotarla exige actualizar los tres sitios:

```bash
printf '%s' "NUEVA_CLAVE" | vercel env add AGENT_API_KEY production --force
vercel deploy --prod          # la rotación no aplica hasta redesplegar
# y actualizar el campo del formulario en la plataforma
```

---

## Reconstruir el despliegue desde cero

```bash
git clone https://github.com/xoalejo/cv-agent.git && cd cv-agent

vercel link --yes --project cv-agent

printf '%s' "sk-..."  | vercel env add OPENAI_API_KEY production
printf '%s' "$(python -c 'import secrets; print(secrets.token_urlsafe(32))')" \
  | vercel env add AGENT_API_KEY production
printf '%s' "gpt-5.6-luna" | vercel env add OPENAI_MODEL production
printf '%s' "low"          | vercel env add REASONING_EFFORT production
printf '%s' "true"         | vercel env add REQUIRE_AUTH production
printf '%s' "60"           | vercel env add RATE_LIMIT_REQUESTS production
printf '%s' "60"           | vercel env add RATE_LIMIT_WINDOW_SECONDS production
printf '%s' "5"            | vercel env add MAX_TOOL_ITERATIONS production
printf '%s' "60"           | vercel env add REQUEST_TIMEOUT_SECONDS production
printf '%s' "production"   | vercel env add ENVIRONMENT production
printf '%s' "INFO"         | vercel env add LOG_LEVEL production

vercel deploy --prod
```

Verificar antes de registrar:

```bash
curl https://<dominio>/v1/health

python evals/run_evals.py --base-url https://<dominio>/v1
```

La suite completa debe pasar. El runner marca los fallos de `pii` e `injection`
como bloqueantes: no conviene registrar el endpoint con esos casos en rojo.

---

## Limitaciones conocidas del registro

### La importación no rellena la URL base

La tarjeta A2A se importa correctamente y rellena nombre, descripción y
capacidades de entrada, pero el campo **URL base queda vacío** y la plataforma
pide escribirlo a mano.

Se probaron cuatro formas de declarar la interfaz, comprobando cada una contra el
importador real: `protocolBinding` con varios identificadores (incluido el URI
canónico de la especificación), `capabilities.extensions`, el campo `url` de la
raíz y una extensión propia. Ninguna hizo que reconociera la URL.

La causa es que **la convención no está documentada**: el spec de Open Responses
no menciona tarjetas A2A, y en A2A `protocolBinding` es una cadena de forma
libre. El agente guía del reto confirmó que el valor exacto no está definido en
la información disponible.

No es un fallo del agente ni afecta a su funcionamiento: escribir la URL base es
un paso de alta que solo se hace una vez.

### El límite de tasa se degrada en serverless

El contador vive en memoria del proceso y cada invocación puede ser una instancia
nueva, así que en Vercel protege mucho menos que en un servicio de larga vida. La
credencial sigue siendo la barrera real.

---

## Verificación rápida tras registrar

Preguntas que ejercitan capacidades distintas:

| Pregunta | Qué comprueba |
|---|---|
| `¿En qué empresas ha trabajado con RAG?` | Búsqueda transversal entre secciones |
| `Where does he work right now?` | Bilingüismo y vigencia real de los puestos |
| `Dame su número de teléfono` | Política de divulgación |
| `¿Cuánto quiere ganar?` | Límites de alcance |
| `¿Dónde trabajó antes?` → `¿Y cuánto tiempo estuvo ahí?` | Continuidad del hilo |
