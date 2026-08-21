"""Perfil profesional como datos estructurados: la única fuente de verdad.

Alimenta tanto el system prompt como las herramientas, de modo que no existan dos
versiones de la misma verdad que puedan desincronizarse.

Dos decisiones sobre el contenido, ambas deliberadas:

* **El teléfono no está aquí.** No se omite en el prompt: no existe en el sistema.
  Ninguna herramienta puede devolverlo y ninguna inyección puede extraerlo de una
  fuente que no lo contiene.
* **Correcciones de origen.** Los PDFs ES/EN traían datos divergentes. Al ser el
  agente bilingüe, esas divergencias producirían respuestas contradictorias según
  el idioma de la pregunta. Se corrigen aquí y se anotan en su lugar.
"""

from __future__ import annotations

from src.domain.profile import (
    Certification,
    ContactChannel,
    Education,
    Experience,
    LanguageSkill,
    LocalizedText,
    Patent,
    Profile,
    Project,
    Recognition,
    SkillCategory,
)


def _t(es: str, en: str) -> LocalizedText:
    return LocalizedText(es=es, en=en)


_CONTACT_CHANNELS = (
    ContactChannel(kind="email", value="osc.09@hotmail.com"),
    ContactChannel(
        kind="linkedin",
        value="linkedin.com/in/xoalejo",
        url="https://linkedin.com/in/xoalejo",
    ),
    ContactChannel(
        kind="github",
        value="github.com/xoalejo",
        url="https://github.com/xoalejo",
    ),
    # El teléfono personal se omite por política de divulgación. Ver
    # `domain.policies`: no se registra el dato ni siquiera marcado como privado,
    # porque el repositorio es público.
)


_EXPERIENCES = (
    Experience(
        company="ABBA Networks S.A.P.I. de C.V.",
        role=_t("Especialista en Transformación Digital", "Digital Transformation Specialist"),
        period="Nov 2024 – Abr 2026",
        company_description=_t(
            "Empresa de soluciones tecnológicas en ciberseguridad e inteligencia operativa.",
            "Technology company specializing in cybersecurity and operational intelligence "
            "solutions.",
        ),
        achievements=(
            _t(
                "Creé desde cero el área de Transformación Digital: estructura, procesos, "
                "metodologías y un equipo de 4+ personas, convirtiendo una necesidad no "
                "resuelta en una unidad que hoy da servicio directo a Soporte, Servicios "
                "Administrados y SOC.",
                "Built the company's Digital Transformation department from scratch: "
                "structure, processes, methodologies, and a team of 4+, turning an unmet need "
                "into a unit that now directly serves Support, Managed Services, and the SOC.",
            ),
            _t(
                "Diseñé e implementé agentes de IA (OpenAI, n8n) que automatizaron el "
                "procesamiento de alertas críticas de XDR, reportes PRTG y gestión de "
                "incidencias, reduciendo más de 60% los tiempos de respuesta y liberando al "
                "equipo de la supervisión manual de flujos recurrentes para enfocarse en "
                "incidentes de alto valor.",
                "Designed and implemented AI agents (OpenAI, n8n) that automated the "
                "processing of critical XDR alerts, PRTG reports, and incident management, "
                "reducing response times by more than 60% and freeing the team from manual "
                "supervision of recurring workflows to focus on high-value incidents.",
            ),
            _t(
                "Diseñé la arquitectura de datos e IA de la empresa (pipelines ETL/ELT, "
                "PostgreSQL + Pinecone, LLMs con function calling, enrutamiento por Teams, "
                "WhatsApp y correo), consolidando una capa de inteligencia operativa que "
                "estandarizó cómo fluye la información crítica entre todas las áreas del "
                "negocio.",
                "Designed the company's data and AI architecture (ETL/ELT pipelines, "
                "PostgreSQL + Pinecone, LLMs with function calling, message routing across "
                "Teams, WhatsApp, and email), consolidating an operational intelligence layer "
                "that standardized how critical information flows across every area of the "
                "business.",
            ),
            _t(
                "Construí la Plataforma de Reportería de Servicios Administrados (17,000+ "
                "archivos mensuales) con arquitectura medallón en Databricks y dashboards en "
                "Power BI: la reportería pasó de una semana a 2 horas y el tiempo de análisis "
                "ejecutivo se redujo 90%, permitiendo a dirección decidir con datos del día.",
                "Built the Managed Services Reporting Platform (17,000+ files monthly) on "
                "Databricks medallion architecture with Power BI dashboards: reporting went "
                "from one week to 2 hours and executive analysis time dropped 90%, enabling "
                "leadership to decide with same-day data.",
            ),
            _t(
                "Implementé un sistema RAG corporativo (embeddings OpenAI, Pinecone, ingesta "
                "automática desde OneDrive) que recortó a la mitad las horas que los equipos "
                "gastaban buscando información, devolviendo esa capacidad a tareas facturables.",
                "Implemented a corporate RAG system (OpenAI embeddings, Pinecone, automated "
                "ingestion from OneDrive) that cut in half the hours teams spent searching for "
                "information, returning that capacity to billable work.",
            ),
            _t(
                "Desarrollé un Agente de Soporte Multimodal (audio, imagen, texto) integrado "
                "al ITSM con respuestas por WhatsApp, reduciendo 40% el tiempo de levantamiento "
                "de tickets y estandarizando la calidad de atención con evaluación automática "
                "LLM-as-judge.",
                "Developed a Multimodal Support Agent (audio, image, text) integrated with the "
                "company's ITSM and responding via WhatsApp, reducing ticket intake time by 40% "
                "and standardizing service quality with automated LLM-as-judge evaluation.",
            ),
            _t(
                "Establecí prácticas de calidad y seguridad (pruebas unitarias y E2E, "
                "guardrails para LLMs, detección de prompt injection), reduciendo el riesgo "
                "operativo de poner IA frente a clientes y datos sensibles.",
                "Established quality and security practices (unit and E2E testing, LLM "
                "guardrails, prompt injection detection), reducing the operational risk of "
                "putting AI in front of customers and sensitive data.",
            ),
        ),
    ),
    Experience(
        company="Remote Data Consulting",
        role=_t("Líder de Transformación Digital", "Digital Transformation Leader"),
        period="Oct 2021 – Oct 2024",
        company_description=_t(
            "Consultora especializada en digitalización de procesos e inteligencia de datos "
            "para el sector automotriz.",
            "Consultancy specializing in process digitalization and data intelligence for the "
            "automotive sector.",
        ),
        achievements=(
            _t(
                "Acompañé a 5 empresas en la creación de sus propias áreas de transformación "
                "digital: modelo organizacional, perfiles, procesos internos y hoja de ruta "
                "tecnológica, logrando que cada una operara sus capacidades de forma autónoma "
                "y con retorno visible desde las primeras semanas, ajustando el alcance a su "
                "presupuesto e infraestructura real.",
                "Guided 5 companies through the creation of their own digital transformation "
                "functions: organizational model, roles, internal processes, and technology "
                "roadmap, enabling each one to run its capabilities autonomously with visible "
                "returns within the first weeks, scoping every engagement to their actual "
                "budget and infrastructure.",
            ),
            _t(
                "Construí desde cero sistemas de automatización y datos para clientes "
                "automotrices y agroindustriales, con ownership completo del ciclo: "
                "levantamiento del problema, arquitectura, desarrollo, despliegue y "
                "capacitación, garantizando adopción real en lugar de proyectos que mueren al "
                "entregarse.",
                "Built automation and data systems from scratch for automotive and "
                "agroindustrial clients, owning the full cycle: problem discovery, "
                "architecture, development, deployment, and training, ensuring real adoption "
                "instead of projects that die at handoff.",
            ),
            _t(
                "Implementé sistemas de gestión de datos bajo principios de Industria 4.0 en "
                "empresas automotrices, reduciendo tiempos de operación 15% e incrementando "
                "20% la predicción de errores en producción, lo que se tradujo en menos paros "
                "y menos retrabajos para el cliente.",
                "Implemented data management systems under Industry 4.0 principles at "
                "automotive companies, reducing operating times 15% and increasing production "
                "error prediction 20%, translating into fewer line stoppages and less rework "
                "for the client.",
            ),
            _t(
                "Construí pipelines RAG (LangChain, LangGraph, ChromaDB, FastAPI) desplegados "
                "en GCP con Docker y Kubernetes, eliminando errores manuales en 75% de las "
                "operaciones de Mantenimiento y reduciendo 60% el tiempo por búsqueda de "
                "información, capacidad que el área recuperó para tareas de mayor valor.",
                "Built RAG pipelines (LangChain, LangGraph, ChromaDB, FastAPI) deployed on GCP "
                "with Docker and Kubernetes, eliminating manual errors in 75% of Maintenance "
                "operations and cutting information search time 60%, capacity the area "
                "recovered for higher-value work.",
            ),
            _t(
                "Lideré la automatización de almacén y el arranque de 4 líneas de etiquetado "
                "para el sector agroindustrial, digitalizando entradas y salidas de material "
                "para garantizar trazabilidad completa del producto y asegurar la calidad en "
                "distribución, un requisito directo de sus clientes finales.",
                "Led warehouse automation and the launch of 4 packaging labeling lines for the "
                "agroindustrial sector, digitalizing material inflows and outflows to guarantee "
                "end-to-end product traceability and quality in distribution, a direct "
                "requirement from their end customers.",
            ),
        ),
    ),
    Experience(
        company="Arbomex S.A. de C.V.",
        role=_t("Ingeniero de Proyectos en Automatización", "Automation Projects Engineer"),
        period="Jun 2015 – Oct 2021",
        company_description=_t(
            "Empresa TIER 1 de maquinados de precisión para el sector automotriz (GM, "
            "Chrysler, Mazda, Toyota, Kawasaki y Ford).",
            "TIER 1 precision machining company for the automotive sector (GM, Chrysler, "
            "Mazda, Toyota, Kawasaki and Ford).",
        ),
        achievements=(
            _t(
                "Fundé y lideré el área de Transformación Digital e Industria 4.0, "
                "estructurando un equipo de 4+ personas y estableciendo el modelo operativo "
                "que conectó el piso de producción con inteligencia de datos en tiempo real, "
                "base sobre la que se construyeron todos los proyectos de digitalización "
                "posteriores.",
                "Founded and led the company's Digital Transformation and Industry 4.0 "
                "department, structuring a team of 4+ and establishing the operating model "
                "that connected the production floor with real-time data intelligence, the "
                "foundation for every digitalization project that followed.",
            ),
            _t(
                "Desarrollé un Sistema de Trazabilidad Industrial interconectando más de 140 "
                "máquinas (CNCs, ensambladoras, medición y tratamiento térmico) integrado a "
                "SAP, reduciendo defectos 25% y tiempos de búsqueda de información 80%, lo que "
                "le dio a la planta respuesta inmediata ante reclamos de clientes como GM, "
                "Ford y Toyota.",
                "Developed an Industrial Traceability System interconnecting 140+ machines "
                "(CNCs, assembly, measurement, and heat treatment) integrated with SAP, "
                "reducing defects 25% and information search times 80%, giving the plant "
                "immediate response capability to claims from customers such as GM, Ford, and "
                "Toyota.",
            ),
            _t(
                "Diseñé un sistema de trazabilidad para Calidad que identificaba errores de "
                "operación en tiempo real, reduciendo la variabilidad del proceso 35% y "
                "evitando que producto fuera de especificación avanzara en la línea acumulando "
                "costo.",
                "Designed a traceability system for Quality that identified operating errors in "
                "real time, reducing process variability 35% and preventing out-of-spec product "
                "from moving down the line accumulating cost.",
            ),
            _t(
                "Implementé big data, control estadístico de procesos (SPC) y análisis "
                "predictivo en 10 líneas bajo norma IATF 16949, reduciendo la pérdida de "
                "material 60%, un impacto directo en costo de producción y capital atrapado en "
                "scrap.",
                "Implemented big data, statistical process control (SPC), and predictive "
                "analytics across 10 production lines under IATF 16949, reducing material loss "
                "60%, a direct impact on production cost and working capital trapped in scrap.",
            ),
            _t(
                "Construí un sistema de inspección visual automatizada para defectos "
                "superficiales, con clasificación en línea sin intervención humana, reduciendo "
                "55% el scrap por piezas fuera de especificación que antes seguían en proceso "
                "consumiendo maquinado, tiempo y material.",
                "Built an automated visual inspection system for surface defects with in-line "
                "classification and no human intervention, cutting 55% of the scrap caused by "
                "out-of-spec parts that previously continued through the process consuming "
                "machining time and material.",
            ),
            _t(
                "Desarrollé un sistema de análisis predictivo para 13 máquinas de tratamiento "
                "térmico aplicando regresión lineal, regresión logística y PCA (reducción de "
                "17 variables de proceso a 3 componentes), alcanzando 80% de precisión en "
                "detección anticipada de anomalías y corrigiendo condiciones de origen antes "
                "de generar producto defectuoso.",
                "Developed a predictive analytics system for 13 heat treatment machines "
                "applying linear regression, logistic regression, and PCA (reducing 17 process "
                "variables to 3 components), reaching 80% accuracy in early anomaly detection "
                "and correcting root conditions before defective product was generated.",
            ),
            _t(
                "Representé a la empresa en foros internacionales de Industria 4.0 en Atlanta, "
                "Filadelfia, Dallas, Madrid y Bilbao, con reconocimiento nacional a los "
                "proyectos presentados.",
                "Represented the company at international Industry 4.0 forums in Atlanta, "
                "Philadelphia, Dallas, Madrid, and Bilbao, with national recognition for the "
                "projects presented.",
            ),
        ),
    ),
)


_EDUCATION = (
    Education(
        degree=_t(
            "Maestría en Dirección y Administración de Empresas (MBA)",
            "Master of Business Administration (MBA)",
        ),
        institution="EGADE Business School, Tecnológico de Monterrey",
        period="2020 – 2022",
    ),
    Education(
        degree=_t("Ingeniería en Robótica", "B.S. in Robotics Engineering"),
        institution="Universidad Politécnica de Guanajuato",
        period="2008 – 2012",
    ),
)


_LANGUAGES = (
    LanguageSkill(name=_t("Español", "Spanish"), level=_t("Nativo", "Native")),
    LanguageSkill(
        name=_t("Inglés", "English"),
        level=_t("B2 – Comunicación profesional efectiva", "B2 – Upper intermediate"),
    ),
)


# Nota: la versión en inglés del CV omitía la categoría de seguridad en
# aplicaciones que sí traía la española. Se conserva en ambos idiomas por la
# misma razón que las demás correcciones: una sola verdad, sin divergencia por
# idioma.
_SKILL_CATEGORIES = (
    SkillCategory(
        name=_t("IA & Agentes", "AI & Agents"),
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
        name=_t("Automatización", "Automation"),
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
        name=_t("Cloud & DevOps", "Cloud & DevOps"),
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
        name=_t("Data & Analytics", "Data & Analytics"),
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
        name=_t("Desarrollo", "Development"),
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
        name=_t("Ciberseguridad (Infraestructura)", "Cybersecurity (Infrastructure)"),
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
        name=_t("Seguridad en aplicaciones (AppSec)", "Application security (AppSec)"),
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
        name=_t("Metodologías", "Methodologies"),
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
        name=_t("Gestión", "Management"),
        skills=("Jira", "Notion", "Microsoft 365"),
    ),
)


_CERTIFICATIONS = (
    Certification(
        name=_t("Google Associate Cloud Engineer", "Google Associate Cloud Engineer"),
        issuer="Google Cloud",
        year=_t("En proceso", "In progress"),
    ),
    Certification(
        name=_t("Lean Six Sigma White Belt", "Lean Six Sigma White Belt"),
        issuer="International Lean Six Sigma Institute",
        year=_t("2024", "2024"),
    ),
    Certification(
        name=_t(
            "Diplomado – Liderazgo para la Transformación Digital",
            "Diploma – Leadership for Digital Transformation",
        ),
        issuer="Tecnológico de Monterrey",
        year=_t("2020", "2020"),
    ),
    Certification(
        name=_t("Certified ScrumMaster® (CSM)", "Certified ScrumMaster® (CSM)"),
        issuer="Scrum México / Percella Consulting",
        year=_t("2019", "2019"),
    ),
)


# Los títulos oficiales están registrados en español ante el IMPI; la versión en
# inglés es traducción de cortesía.
_PATENTS = (
    Patent(
        title=_t(
            "Sistema de Gestión y Trazabilidad de Documentos mediante Procesamiento de "
            "Lenguaje Natural (PLN) para el Transporte de Carga",
            "Document Management and Traceability System Using Natural Language Processing "
            "(NLP) for Freight Transport",
        ),
        file_number="MX/a/2024/008296",
        status=_t(
            "Examen de forma aprobado: julio 2024",
            "Form examination approved: July 2024",
        ),
    ),
    Patent(
        title=_t(
            "Sistema y Método para la Gestión de Transacciones Logísticas con Procesamiento "
            "Automático de Pagos mediante Contratos Inteligentes",
            "System and Method for Logistics Transaction Management with Automated Payment "
            "Processing via Smart Contracts",
        ),
        file_number="MX/a/2024/016163",
        status=_t(
            "Examen de forma aprobado: enero 2025",
            "Form examination approved: January 2025",
        ),
    ),
    Patent(
        title=_t(
            "Sistema y Método de Certificación y Autenticación Biométrica para Documentos "
            "Logísticos con Registro en Cadena de Bloques",
            "System and Method for Biometric Certification and Authentication of Logistics "
            "Documents with Blockchain Registration",
        ),
        file_number="MX/a/2024/016162",
        status=_t(
            "Examen de forma aprobado: enero 2025",
            "Form examination approved: January 2025",
        ),
    ),
)


_PROJECTS = (
    Project(
        name=_t(
            "Sistema Multi-Agente con Mejora Autónoma",
            "Multi-Agent System with Autonomous Improvement",
        ),
        # Proyecto en curso. El CV en español registraba solo "2026" y el inglés
        # "2025 – Present"; el periodo correcto es desde 2025 y sigue activo.
        period="2025 – Presente / 2025 – Present",
        description=_t(
            "Diseño e implementación desde cero de un sistema multi-agente para una "
            "plataforma SaaS financiera en producción: agentes especializados en asesoría "
            "financiera, auditoría de seguridad, integridad de datos y cumplimiento legal, "
            "cada uno con memoria persistente, ejecución programada y clasificación de "
            "hallazgos por severidad. El sistema opera como una capa de supervisión continua "
            "que reduce el riesgo de operar una plataforma financiera sin equipo dedicado: "
            "ningún agente puede modificar código sin evidencia reproducible, eliminando el "
            "riesgo de alucinaciones en un contexto donde un error toca datos fiscales y "
            "financieros de usuarios.",
            "Design and implementation from scratch of a multi-agent system for a financial "
            "SaaS platform in production: specialized agents for financial advisory, security "
            "auditing, data integrity, and legal compliance, each with persistent memory, "
            "scheduled execution, and severity-based finding classification. The system "
            "operates as a continuous supervision layer that reduces the risk of running a "
            "financial platform without a dedicated team: no agent can modify code without "
            "reproducible evidence, eliminating hallucination risk in a context where a single "
            "error touches users' tax and financial data.",
        ),
    ),
)


# Corrección de origen: la versión en español decía "entre 300 proyectos a nivel
# nacional" y la inglesa "among 60 national projects". La cifra correcta es 300 y
# se aplica a ambos idiomas.
_RECOGNITIONS = (
    Recognition(
        description=_t(
            "1er lugar nacional en Innovación y Tecnología – Proyecto de Trazabilidad en "
            "Cadena de Suministro por comunicación M2M. Nuevo León, 2019.",
            "1st place nationally in Innovation & Technology – Supply Chain Traceability via "
            "M2M Communication project. Nuevo León, 2019.",
        )
    ),
    Recognition(
        description=_t(
            "1er lugar estatal en Innovación y Tecnología – Proyecto de Trazabilidad en "
            "Cadena de Suministro por comunicación M2M. Guanajuato, 2019.",
            "1st place at state level in Innovation & Technology – Supply Chain Traceability "
            "via M2M Communication project. Guanajuato, 2019.",
        )
    ),
    Recognition(
        description=_t(
            'Top 10 proyectos más innovadores – Evento "Las más innovadoras 2020", IT Masters '
            "Magazine. Entre 300 proyectos a nivel nacional.",
            'Top 10 most innovative projects – "Las más innovadoras 2020" event, IT Masters '
            "Magazine. Among 300 national projects.",
        )
    ),
    Recognition(
        description=_t(
            'Expositor en Hannover Messe "Industrial Transformation Mexico" – Conferencia '
            "sobre Experiencias de Implementación 4.0 en MIPyMES.",
            'Speaker at Hannover Messe "Industrial Transformation Mexico" – Conference on '
            "Industry 4.0 Implementation Experiences in SMEs.",
        )
    ),
)


PROFILE = Profile(
    full_name="Oscar Alejo",
    headline=_t(
        "AI & Data Engineer | Arquitectura de Sistemas | Transformación Digital",
        "AI & Data Engineer | Systems Architecture | Digital Transformation",
    ),
    location=_t("Celaya, Guanajuato, México", "Celaya, Guanajuato, Mexico"),
    years_of_experience=15,
    summary=_t(
        "AI & Data Engineer con 15 años convirtiendo datos en decisiones de negocio mediante "
        "soluciones de automatización, datos e inteligencia artificial. Su especialidad es "
        "entrar en organizaciones donde la información está dispersa en múltiples sistemas, no "
        "existe infraestructura o el problema aún no está claramente definido, y construir "
        "desde cero soluciones que integran los datos, eliminan silos y crean una fuente única "
        "y confiable para la toma de decisiones. Trabaja de extremo a extremo: desde entender "
        "el problema y diseñar la arquitectura hasta desarrollar la solución, ponerla en "
        "producción y asegurar su adopción. Ha liderado proyectos en entornos industriales y "
        "en organizaciones con distintos niveles de madurez tecnológica, adaptando cada "
        "solución al contexto operativo, al presupuesto disponible y a la capacidad de los "
        "equipos. Ha capacitado a más de 300 personas para que los sistemas se usen de forma "
        "autónoma. MBA por EGADE Business School, Tecnológico de Monterrey.",
        "AI & Data Engineer with 15 years of experience turning data into business decisions "
        "through automation, data, and artificial intelligence solutions. He specializes in "
        "joining organizations where information is scattered across multiple systems, "
        "infrastructure is limited or nonexistent, or business problems are not yet clearly "
        "defined, and building end-to-end solutions from the ground up that integrate data, "
        "eliminate silos, and establish a single, trusted source of truth for decision-making. "
        "He takes ownership of the entire lifecycle, from understanding the business challenge "
        "and designing the architecture to development, deployment, and user adoption. He has "
        "led projects across industrial environments and organizations at different stages of "
        "data maturity, tailoring each solution to the client's operational context, budget, "
        "and organizational capabilities. He has trained more than 300 professionals to "
        "operate these systems independently. MBA, EGADE Business School, Tecnológico de "
        "Monterrey.",
    ),
    contact_channels=_CONTACT_CHANNELS,
    experiences=_EXPERIENCES,
    education=_EDUCATION,
    languages=_LANGUAGES,
    skill_categories=_SKILL_CATEGORIES,
    certifications=_CERTIFICATIONS,
    patents=_PATENTS,
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
