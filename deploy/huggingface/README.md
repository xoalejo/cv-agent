---
title: CV Agent
emoji: 💼
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
short_description: Agente conversacional de CV compatible con Open Responses
---

# CV Agent

Agente conversacional sobre la trayectoria profesional de Oscar Alejo, expuesto
como endpoint HTTP compatible con el contrato
[Open Responses](https://www.openresponses.org/).

Este Space es solo el entorno de ejecución. El código, la documentación de
arquitectura y las decisiones técnicas están en el repositorio:
**https://github.com/xoalejo/cv-agent**

## Uso

```bash
curl -X POST https://xoalejo-cv-agent.hf.space/responses \
  -H "Authorization: Bearer $AGENT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"input": "¿En qué empresas ha trabajado con RAG?"}'
```

El endpoint requiere autenticación Bearer. La sonda `/health` responde sin
credencial.

## Configuración

Las variables sensibles se definen como *secrets* del Space, nunca en el
repositorio:

| Secret | Descripción |
|---|---|
| `OPENAI_API_KEY` | Clave de la API de OpenAI |
| `AGENT_API_KEY` | Bearer token que exige este endpoint |
