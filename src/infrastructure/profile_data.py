"""Perfil profesional como datos estructurados: la única fuente de verdad.

Alimenta tanto el system prompt como las herramientas, de modo que no existan dos
versiones de la misma verdad que puedan desincronizarse.

Dos decisiones sobre el contenido, ambas deliberadas:

* **El teléfono no está aquí.** No se omite en el prompt: no existe en el sistema.
  Ninguna herramienta puede devolverlo y ninguna inyección puede extraerlo de una
  fuente que no lo contiene.
* **Solo español.** Es el idioma canónico del CV. El agente traduce al responder
  en otro idioma, en lugar de arrastrar una segunda copia que habría que
  mantener sincronizada. Menos superficie de error y un prompt sensiblemente más
  corto en cada llamada.
"""

from __future__ import annotations

from src.domain.profile import (
    Certification,
    ContactChannel,
    Education,
    Experience,
    LanguageSkill,
    Profile,
    Project,
    Recognition,
    SkillCategory,
)

_CONTACT_CHANNELS = (
    ContactChannel(kind="email", value="osc.09@hotmail.com", url=None),
    ContactChannel(
        kind="linkedin", value="linkedin.com/in/xoalejo", url="https://linkedin.com/in/xoalejo"
    ),
    ContactChannel(
        kind="github", value="github.com/xoalejo", url="https://github.com/xoalejo"
    ),
    # El teléfono personal se omite por política de divulgación. Ver
    # `domain.policies`: no se registra el dato ni siquiera marcado como privado,
    # porque el repositorio es público.
)


_EXPERIENCES = (
    Experience(
        company="ABBA Networks S.A.P.I. de C.V.",
        role="Especialista en Transformación Digital",
        period="Nov 2024 – Abr 2026",
        company_description=(
            "Empresa de soluciones tecnológicas en ciberseguridad e inteligencia operativa."
        ),
        achievements=(
            (
                "Creé desde cero el área de Transformación Digital: estructura, "
                "procesos, metodologías y un equipo de 4+ personas, "
                "convirtiendo una necesidad no resuelta en una unidad que hoy "
                "da servicio directo a Soporte, Servicios Administrados y SOC."
            ),
            (
                "Diseñé e implementé agentes de IA (OpenAI, n8n) que "
                "automatizaron el procesamiento de alertas críticas de XDR, "
                "reportes PRTG y gestión de incidencias, reduciendo más de 60% "
                "los tiempos de respuesta y liberando al equipo de la "
                "supervisión manual de flujos recurrentes para enfocarse en "
                "incidentes de alto valor."
            ),
            (
                "Diseñé la arquitectura de datos e IA de la empresa (pipelines "
                "ETL/ELT, PostgreSQL + Pinecone, LLMs con function calling, "
                "enrutamiento por Teams, WhatsApp y correo), consolidando una "
                "capa de inteligencia operativa que estandarizó cómo fluye la "
                "información crítica entre todas las áreas del negocio."
            ),
            (
                "Construí la Plataforma de Reportería de Servicios "
                "Administrados (17,000+ archivos mensuales) con arquitectura "
                "medallón en Databricks y dashboards en Power BI: la reportería "
                "pasó de una semana a 2 horas y el tiempo de análisis ejecutivo "
                "se redujo 90%, permitiendo a dirección decidir con datos del "
                "día."
            ),
            (
                "Implementé un sistema RAG corporativo (embeddings OpenAI, "
                "Pinecone, ingesta automática desde OneDrive) que recortó a la "
                "mitad las horas que los equipos gastaban buscando información, "
                "devolviendo esa capacidad a tareas facturables."
            ),
            (
                "Desarrollé un Agente de Soporte Multimodal (audio, imagen, "
                "texto) integrado al ITSM con respuestas por WhatsApp, "
                "reduciendo 40% el tiempo de levantamiento de tickets y "
                "estandarizando la calidad de atención con evaluación "
                "automática LLM-as-judge."
            ),
            (
                "Establecí prácticas de calidad y seguridad (pruebas unitarias "
                "y E2E, guardrails para LLMs, detección de prompt injection), "
                "reduciendo el riesgo operativo de poner IA frente a clientes y "
                "datos sensibles."
            ),
        ),
    ),
    Experience(
        company="Remote Data Consulting",
        role="Líder de Transformación Digital",
        period="Oct 2021 – Oct 2024",
        company_description=(
            "Consultora especializada en digitalización de procesos e "
            "inteligencia de datos para el sector automotriz."
        ),
        achievements=(
            (
                "Acompañé a 5 empresas en la creación de sus propias áreas de "
                "transformación digital: modelo organizacional, perfiles, "
                "procesos internos y hoja de ruta tecnológica, logrando que "
                "cada una operara sus capacidades de forma autónoma y con "
                "retorno visible desde las primeras semanas, ajustando el "
                "alcance a su presupuesto e infraestructura real."
            ),
            (
                "Construí desde cero sistemas de automatización y datos para "
                "clientes automotrices y agroindustriales, con ownership "
                "completo del ciclo: levantamiento del problema, arquitectura, "
                "desarrollo, despliegue y capacitación, garantizando adopción "
                "real en lugar de proyectos que mueren al entregarse."
            ),
            (
                "Implementé sistemas de gestión de datos bajo principios de "
                "Industria 4.0 en empresas automotrices, reduciendo tiempos de "
                "operación 15% e incrementando 20% la predicción de errores en "
                "producción, lo que se tradujo en menos paros y menos "
                "retrabajos para el cliente."
            ),
            (
                "Construí pipelines RAG (LangChain, LangGraph, ChromaDB, "
                "FastAPI) desplegados en GCP con Docker y Kubernetes, "
                "eliminando errores manuales en 75% de las operaciones de "
                "Mantenimiento y reduciendo 60% el tiempo por búsqueda de "
                "información, capacidad que el área recuperó para tareas de "
                "mayor valor."
            ),
            (
                "Lideré la automatización de almacén y el arranque de 4 líneas "
                "de etiquetado para el sector agroindustrial, digitalizando "
                "entradas y salidas de material para garantizar trazabilidad "
                "completa del producto y asegurar la calidad en distribución, "
                "un requisito directo de sus clientes finales."
            ),
        ),
    ),
    Experience(
        company="Arbomex S.A. de C.V.",
        role="Ingeniero de Proyectos en Automatización",
        period="Jun 2015 – Oct 2021",
        company_description=(
            "Empresa TIER 1 de maquinados de precisión para el sector "
            "automotriz (GM, Chrysler, Mazda, Toyota, Kawasaki y Ford)."
        ),
        achievements=(
            (
                "Fundé y lideré el área de Transformación Digital e Industria "
                "4.0, estructurando un equipo de 4+ personas y estableciendo el "
                "modelo operativo que conectó el piso de producción con "
                "inteligencia de datos en tiempo real, base sobre la que se "
                "construyeron todos los proyectos de digitalización "
                "posteriores."
            ),
            (
                "Desarrollé un Sistema de Trazabilidad Industrial "
                "interconectando más de 140 máquinas (CNCs, ensambladoras, "
                "medición y tratamiento térmico) integrado a SAP, reduciendo "
                "defectos 25% y tiempos de búsqueda de información 80%, lo que "
                "le dio a la planta respuesta inmediata ante reclamos de "
                "clientes como GM, Ford y Toyota."
            ),
            (
                "Diseñé un sistema de trazabilidad para Calidad que "
                "identificaba errores de operación en tiempo real, reduciendo "
                "la variabilidad del proceso 35% y evitando que producto fuera "
                "de especificación avanzara en la línea acumulando costo."
            ),
            (
                "Implementé big data, control estadístico de procesos (SPC) y "
                "análisis predictivo en 10 líneas bajo norma IATF 16949, "
                "reduciendo la pérdida de material 60%, un impacto directo en "
                "costo de producción y capital atrapado en scrap."
            ),
            (
                "Construí un sistema de inspección visual automatizada para "
                "defectos superficiales, con clasificación en línea sin "
                "intervención humana, reduciendo 55% el scrap por piezas fuera "
                "de especificación que antes seguían en proceso consumiendo "
                "maquinado, tiempo y material."
            ),
            (
                "Desarrollé un sistema de análisis predictivo para 13 máquinas "
                "de tratamiento térmico aplicando regresión lineal, regresión "
                "logística y PCA (reducción de 17 variables de proceso a 3 "
                "componentes), alcanzando 80% de precisión en detección "
                "anticipada de anomalías y corrigiendo condiciones de origen "
                "antes de generar producto defectuoso."
            ),
            (
                "Representé a la empresa en foros internacionales de Industria "
                "4.0 en Atlanta, Filadelfia, Dallas, Madrid y Bilbao, con "
                "reconocimiento nacional a los proyectos presentados."
            ),
        ),
    ),
)


_EDUCATION = (
    Education(
        degree=(
            "Maestría en Dirección y Administración de Empresas (MBA). "
            "Cédula profesional 13365841."
        ),
        institution="EGADE Business School, Tecnológico de Monterrey",
        period="2020 – 2022",
    ),
    Education(
        degree="Ingeniería en Robótica. Cédula profesional 8266838.",
        institution="Universidad Politécnica de Guanajuato",
        period="2008 – 2012",
    ),
)


_LANGUAGES = (
    LanguageSkill(name="Español", level="Nativo"),
    LanguageSkill(name="Inglés", level="B2 – Comunicación profesional efectiva"),
)


_SKILL_CATEGORIES = (
    SkillCategory(
        name="IA & Agentes",
        skills=(
            "LLMs (OpenAI, Copilot, Gemini, Claude, Hugging Face)",
            "Orquestación de agentes (LangChain, LangGraph)",
            "RAG pipelines",
            "embeddings",
            "Pinecone",
            "ChromaDB",
            "bases de datos vectoriales",
            "Computer Vision",
            "TensorFlow",
            "Scikit-Learn",
            "FastAPI",
            "Flask",
            "Prompt Engineering",
        ),
    ),
    SkillCategory(
        name="Automatización",
        skills=(
            "Orquestación de flujos (n8n, Airflow, Zapier)",
            "Python",
            "agentes multimodales",
            "event-driven architectures",
            "webhooks",
            "WhatsApp Business API",
            "Microsoft Teams",
            "Outlook",
            "REST APIs",
            "GraphQL",
        ),
    ),
    SkillCategory(
        name="Cloud & DevOps",
        skills=(
            "GCP",
            "AWS",
            "Azure",
            "Orquestación de contenedores (Docker, Kubernetes)",
            "CI/CD",
            "GitHub Actions",
            "Jenkins",
            "Vercel",
            "Sentry",
            "entornos híbridos on-premise / nube",
        ),
    ),
    SkillCategory(
        name="Data & Analytics",
        skills=(
            "PostgreSQL",
            "SQL",
            "NoSQL",
            "Databricks",
            "arquitectura medallón",
            "ETL/ELT",
            "data modeling",
            "data quality validation",
            "Tableau",
            "Power BI",
            "análisis predictivo",
            "big data",
            "regresión lineal",
            "Scikit-Learn",
        ),
    ),
    SkillCategory(
        name="Desarrollo",
        skills=(
            "Next.js",
            "Supabase",
            "Stripe",
            "APIs REST",
            "GraphQL",
            "arquitecturas limpias",
            "automatización de pruebas",
            "integración de sistemas fiscales SAT",
        ),
    ),
    SkillCategory(
        name="Ciberseguridad (Infraestructura)",
        skills=(
            "StellarCyber XDR",
            "Bitdefender",
            "PRTG",
            "monitoreo SOC",
            "inteligencia de amenazas CVE",
            "ISO-27000 & ISO 20000",
        ),
    ),
    SkillCategory(
        name="Seguridad en aplicaciones (AppSec)",
        skills=(
            "Autenticación JWT + MFA/TOTP",
            "RLS multi-tenant",
            "AES-256-GCM",
            "rate limiting con Upstash Redis",
            "validación de inputs con Zod",
            "CSP/HSTS",
            "Cloudflare Turnstile",
            "audit logging inmutable",
            "guardrails para LLMs",
            "sanitización DOMPurify",
        ),
    ),
    SkillCategory(
        name="Metodologías",
        skills=(
            "Scrum",
            "Agile",
            "Waterfall",
            "OKRs",
            "Design Thinking",
            "Lean Six Sigma White Belt",
            "Diseño de Servicios",
        ),
    ),
    SkillCategory(
        name="Gestión",
        skills=(
            "Jira",
            "Notion",
            "Microsoft 365",
        ),
    ),
)


_CERTIFICATIONS = (
    Certification(
        name="Google Associate Cloud Engineer",
        issuer="Google Cloud",
        year="En proceso",
    ),
    Certification(
        name="Lean Six Sigma White Belt",
        issuer="International Lean Six Sigma Institute",
        year="2024",
    ),
    Certification(
        name="Diplomado – Liderazgo para la Transformación Digital",
        issuer="Tecnológico de Monterrey",
        year="2020",
    ),
    Certification(
        name="Certified ScrumMaster® (CSM)",
        issuer="Scrum México / Percella Consulting",
        year="2019",
    ),
)


_PROJECTS = (
    Project(
        name="Sistema Multi-Agente con Mejora Autónoma",
        period="2025 – Presente",
        description=(
            "Diseño e implementación desde cero de un sistema multi-agente para "
            "una plataforma SaaS financiera en producción: agentes "
            "especializados en asesoría financiera, auditoría de seguridad, "
            "integridad de datos y cumplimiento legal, cada uno con memoria "
            "persistente, ejecución programada y clasificación de hallazgos por "
            "severidad. El sistema opera como una capa de supervisión continua "
            "que reduce el riesgo de operar una plataforma financiera sin "
            "equipo dedicado: ningún agente puede modificar código sin "
            "evidencia reproducible, eliminando el riesgo de alucinaciones en "
            "un contexto donde un error toca datos fiscales y financieros de "
            "usuarios."
        ),
    ),
)


_RECOGNITIONS = (
    Recognition(
        description=(
            "1er lugar nacional en Innovación y Tecnología – Proyecto de "
            "Trazabilidad en Cadena de Suministro por comunicación M2M. Nuevo León, "
            "2019."
        )
    ),
    Recognition(
        description=(
            "1er lugar estatal en Innovación y Tecnología – Proyecto de "
            "Trazabilidad en Cadena de Suministro por comunicación M2M. Guanajuato, "
            "2019."
        )
    ),
    Recognition(
        description=(
            'Top 10 proyectos más innovadores – Evento "Las más innovadoras 2020", '
            "IT Masters Magazine. Entre 300 proyectos a nivel nacional."
        )
    ),
    Recognition(
        description=(
            'Expositor en Hannover Messe "Industrial Transformation Mexico" – '
            "Conferencia sobre Experiencias de Implementación 4.0 en MIPyMES."
        )
    ),
)


PROFILE = Profile(
    full_name="Oscar Antonio Alejo Gámez",
    headline="AI & Data Engineer | Arquitectura de Sistemas | Transformación Digital",
    location="Celaya, Guanajuato, México",
    years_of_experience=15,
    summary=(
        "AI & Data Engineer con 15 años convirtiendo datos en decisiones de "
        "negocio mediante soluciones de automatización, datos e inteligencia "
        "artificial. Su especialidad es entrar en organizaciones donde la "
        "información está dispersa en múltiples sistemas, no existe "
        "infraestructura o el problema aún no está claramente definido, y "
        "construir desde cero soluciones que integran los datos, eliminan silos "
        "y crean una fuente única y confiable para la toma de decisiones. "
        "Trabaja de extremo a extremo: desde entender el problema y diseñar la "
        "arquitectura hasta desarrollar la solución, ponerla en producción y "
        "asegurar su adopción. Ha liderado proyectos en entornos industriales y "
        "en organizaciones con distintos niveles de madurez tecnológica, "
        "adaptando cada solución al contexto operativo, al presupuesto "
        "disponible y a la capacidad de los equipos. Ha capacitado a más de 300 "
        "personas para que los sistemas se usen de forma autónoma. MBA por "
        "EGADE Business School, Tecnológico de Monterrey."
    ),
    contact_channels=_CONTACT_CHANNELS,
    experiences=_EXPERIENCES,
    education=_EDUCATION,
    languages=_LANGUAGES,
    skill_categories=_SKILL_CATEGORIES,
    certifications=_CERTIFICATIONS,
    projects=_PROJECTS,
    recognitions=_RECOGNITIONS,
)


class StaticProfileRepository:
    """Implementación de `ProfileRepository` sobre datos en código.

    El perfil es un corpus pequeño y estable: cabe en memoria y cambia cuando
    cambia el CV, no en tiempo de ejecución. Una base de datos aquí añadiría una
    frontera que operar y respaldar sin resolver ningún problema real.
    """

    def get(self) -> Profile:
        return PROFILE
