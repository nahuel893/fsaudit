# FILE SYSTEM AUDIT TOOL — FSAudit
## Product Requirements Document (PRD)
**Versión:** 1.0 | **Fecha:** Marzo 2026 | **Confidencial — Uso interno**

---

## Tabla de Contenidos

1. [Resumen Ejecutivo](#1-resumen-ejecutivo)
2. [Contexto y Problema](#2-contexto-y-problema)
3. [Objetivos del Proyecto](#3-objetivos-del-proyecto)
4. [Alcance y Límites](#4-alcance-y-límites)
5. [Arquitectura del Sistema](#5-arquitectura-del-sistema)
6. [Stack Tecnológico](#6-stack-tecnológico)
7. [Requerimientos Funcionales](#7-requerimientos-funcionales)
8. [Diccionario de Datos](#8-diccionario-de-datos)
9. [Requerimientos No Funcionales](#9-requerimientos-no-funcionales)
10. [Estructura del Reporte Excel](#10-estructura-del-reporte-excel)
11. [Variables para Escalabilidad del Análisis](#11-variables-para-escalabilidad-del-análisis)
12. [Fases y Roadmap](#12-fases-y-roadmap)
13. [Riesgos y Mitigaciones](#13-riesgos-y-mitigaciones)

---

## 1. Resumen Ejecutivo

> FSAudit es una herramienta de auditoría de sistemas de archivos multiplataforma (Windows/Linux) que analiza metadatos del filesystem del usuario para generar reportes detallados sobre volumen, tipología, temporalidad y organización de archivos. No lee el contenido de los archivos; opera exclusivamente sobre metadatos del sistema operativo.

El objetivo estratégico es proveer visibilidad sobre la actividad digital del usuario, detectar patrones de productividad, identificar archivos candidatos a limpieza, y sentar las bases de un sistema de auditoría histórica evolutiva.

FSAudit está diseñado con una arquitectura modular de pipeline, donde cada módulo puede ser probado y reemplazado de forma independiente. El output primario es un reporte Excel multi-hoja complementado con un reporte HTML interactivo.

---

## 2. Contexto y Problema

### 2.1 Marco Teórico

El File System Auditing es una práctica establecida tanto en el ámbito de la seguridad informática como en la gestión de almacenamiento. Conceptos clave:

| Concepto | Definición |
|---|---|
| **Inode (Linux)** | Estructura del kernel que almacena metadatos de un archivo: tamaño, permisos, UID, GID, timestamps. No almacena nombre ni contenido. |
| **MFT (Windows)** | Master File Table del sistema NTFS. Equivalente funcional al inode en Unix; contiene atributos del archivo incluyendo timestamps `$STANDARD_INFORMATION`. |
| **stat()** | Syscall POSIX que retorna la estructura `stat` con todos los metadatos de un archivo. En Python: `os.stat()` / `pathlib.Path.stat()`. |
| **mtime** | Modification time: último momento en que se modificó el contenido del archivo. |
| **ctime** | Change time (Linux): cambio de metadato (no de contenido). Creation time (Windows): fecha real de creación. **CRÍTICO: comportamiento diferente por OS.** |
| **atime** | Access time: último momento en que el archivo fue leído. Puede estar deshabilitado (`noatime` mount option en Linux). |

### 2.2 Problema a Resolver

Los usuarios de sistemas de trabajo (oficina, desarrollo de software) acumulan miles de archivos sin visibilidad sobre su distribución, antigüedad ni relevancia. Las consecuencias típicas son:

- Almacenamiento saturado por archivos nunca utilizados o duplicados.
- Imposibilidad de auditar períodos de alta y baja productividad.
- Riesgo de seguridad por archivos sensibles mal ubicados o con permisos incorrectos.
- Ausencia de métricas objetivas para gestión del conocimiento personal.

---

## 3. Objetivos del Proyecto

### 3.1 Objetivo Principal

Construir una herramienta de línea de comandos (CLI) que analice la carpeta de usuario, clasifique archivos por categorías semánticas, y genere reportes accionables en formato Excel y HTML.

### 3.2 Objetivos Secundarios

- Abstraer las diferencias de timestamps entre Windows (NTFS) y Linux (ext4/btrfs) para producir métricas homogéneas.
- Proveer detección de archivos candidatos a eliminación: sin modificación en X días, tamaño 0 bytes, carpetas vacías.
- Establecer la arquitectura base para evolucionar hacia un sistema de auditoría histórica con base de datos SQLite.
- Diseñar el código como portfolio técnico: modular, testeable, con tipado estricto y documentación.

---

## 4. Alcance y Límites

### 4.1 Dentro del Alcance

| Área | Detalle |
|---|---|
| **Inventario de archivos** | Escaneo recursivo de directorios. Recolección de metadatos por `pathlib`/`os.stat()`. |
| **Clasificación** | Mapeo de extensiones a categorías: Oficina, Código, Multimedia, Datos, Comprimidos, Sistema, Desconocido. |
| **Métricas de volumen** | Conteo y suma de bytes por categoría, por directorio, por período de tiempo. |
| **Análisis temporal** | Distribución de archivos por mes/año de modificación. Detección de archivos inactivos. |
| **Análisis de organización** | Profundidad de árbol, archivos en raíz, carpetas vacías, duplicados por nombre. |
| **Análisis de seguridad** | Permisos de archivo (Linux), archivos ocultos, extensiones ejecutables fuera de lugar. |
| **Reporte Excel** | Archivo `.xlsx` multi-hoja con tablas, métricas agregadas y ranking. |
| **Reporte HTML** | Página standalone con charts interactivos (Plotly o Chart.js embebido). |
| **Reporte JSON** | Output crudo estructurado para integración con otras herramientas. |

### 4.2 Fuera del Alcance (Límites Explícitos)

> Estos límites son decisiones de diseño deliberadas, no limitaciones técnicas. Garantizan privacidad, performance y simplicidad en el MVP.

| Límite | Justificación |
|---|---|
| **NO se lee contenido de archivos** | Preserva privacidad y performance. La herramienta es un analizador de metadatos, no de contenido. |
| **NO se modifican archivos ni metadatos** | La herramienta es read-only por diseño. Cero riesgo de daño al sistema. |
| **NO analiza drives de red ni cloud** | Los tiempos de respuesta de sistemas remotos harían el scan impredecible. Fase 3 posible. |
| **NO ejecuta archivos encontrados** | Principio de mínimo privilegio. |
| **NO requiere permisos de administrador/root** | Opera únicamente sobre archivos accesibles por el usuario actual. Los inaccesibles se omiten y se loguean. |

---

## 5. Arquitectura del Sistema

### 5.1 Patrón Arquitectural: Pipeline Modular

FSAudit implementa el patrón **Pipeline** (también llamado Pipes and Filters). Cada módulo recibe un dataset, lo transforma, y pasa el resultado al siguiente. Los módulos son stateless y no tienen dependencias directas entre sí: se comunican a través de estructuras de datos bien definidas (`dataclasses` o `TypedDict`s).

Este patrón es el apropiado para ETL y procesamiento de datos secuencial. Ventajas: testabilidad unitaria por módulo, intercambiabilidad, fácil depuración y extensibilidad.

```
CLI → Scanner → Classifier → Analyzer → Reporter

Cada módulo puede ser reemplazado sin modificar el resto del pipeline.
```

### 5.2 Descripción de Módulos

| Módulo | Responsabilidad | Detalle técnico |
|---|---|---|
| **CLI** | Punto de entrada | `argparse`. Parámetros: `--path`, `--output-dir`, `--format`, `--depth`, `--exclude`, `--min-size`, `--inactive-days`. |
| **Scanner** | Recolección de metadatos | `os.walk()` con manejo de `PermissionError`. Extrae: `path`, `name`, `extension`, `size_bytes`, `mtime`, `ctime_safe`, `atime`, `depth`, `is_hidden`, `permissions`. |
| **Classifier** | Categorización semántica | Mapeo de extensión → categoría vía diccionario configurable (YAML). Extensiones desconocidas → categoría `'Desconocido'`. Soporta sub-categorías. |
| **Analyzer** | Agregación y métricas | Calcula KPIs por categoría, directorio y período. Detecta: archivos inactivos, 0 bytes, sin extensión, duplicados por nombre, carpetas vacías. |
| **Reporter** | Generación de output | Subclases: `ExcelReporter` (openpyxl), `HTMLReporter` (Jinja2), `JSONReporter`. Interfaz común: `generate(analysis_result, output_path)`. |

### 5.3 Manejo Multiplataforma de Timestamps

El comportamiento de `ctime` es radicalmente diferente según el OS. FSAudit abstrae esto en la función `get_creation_time_safe()`:

| OS | `st_ctime` significa | Estrategia FSAudit |
|---|---|---|
| **Windows (NTFS)** | Fecha de creación real del archivo | Usar `st_ctime` directamente como `creation_time`. |
| **Linux (ext4/btrfs)** | Cambio de metadato (inode change) | Usar `min(st_mtime, st_ctime)` como aproximación. Documentar la limitación. En Fase 3: leer `crtime` vía `statx()` si disponible. |
| **macOS (HFS+/APFS)** | Fecha de creación real (birthtime) | Usar `st_birthtime` vía `os.stat_result` si disponible. |

---

## 6. Stack Tecnológico

| Capa | Librería / Tool | Justificación |
|---|---|---|
| **Runtime** | Python 3.10+ | Soporte nativo para `pathlib`, `os`, `dataclasses` y `match/case` para OS detection. Type hints completos. |
| **Filesystem** | `pathlib` + `os.stat()` | API cross-platform nativa. `pathlib.Path` abstrae separadores de ruta. `os.stat()` provee estructura `stat` homogénea. |
| **Procesamiento** | `collections`, `dataclasses` | `Counter`, `defaultdict` para agregaciones. Dataclasses para contratos de datos entre módulos. |
| **Configuración** | PyYAML | El mapa de extensiones → categorías vive en un YAML externo. Configurable sin tocar código. |
| **Excel Report** | openpyxl | Generación nativa de `.xlsx` sin depender de Excel. Soporta estilos, congelado de filas, autofit. |
| **HTML Report** | Jinja2 | Templating para HTML standalone. Los charts se embeben con Chart.js desde CDN o inline para standalone. |
| **CLI** | argparse | Librería estándar. Sin dependencias adicionales. |
| **Testing** | pytest | Tests unitarios por módulo con fixtures de filesystem temporal (`tmp_path`). |
| **Logging** | logging (stdlib) | Log de archivos con `PermissionError`, rutas problemáticas y resumen de ejecución. |

---

## 7. Requerimientos Funcionales

### 7.1 Scanner (RF-01 a RF-05)

| ID | Nombre | Descripción |
|---|---|---|
| **RF-01** | Scan recursivo | El Scanner debe recorrer toda la estructura de directorios a partir del path dado, sin límite de profundidad por defecto. |
| **RF-02** | Exclusión de rutas | Soportar lista de directorios a excluir (ej: `.git`, `node_modules`, `__pycache__`, `venv`). Configurable por CLI y YAML. |
| **RF-03** | Manejo de errores | Los archivos con `PermissionError` se omiten sin detener el scan. Se registran en el log y en el reporte como 'inaccesibles'. |
| **RF-04** | Timestamps seguros | Implementar `get_creation_time_safe()` que detecta el OS y retorna el timestamp más apropiado como fecha de creación. |
| **RF-05** | Detección de ocultos | Marcar como `is_hidden=True`: prefijo `'.'` en Linux, atributo `FILE_ATTRIBUTE_HIDDEN` en Windows (via `ctypes`). |

### 7.2 Classifier (RF-06 a RF-08)

| ID | Nombre | Descripción |
|---|---|---|
| **RF-06** | Categorización por extensión | Mapear extensión (lowercase) a categoría. Mapa externo en `categories.yaml`. Insensible a mayúsculas. |
| **RF-07** | Categorías obligatorias | El sistema debe soportar: Oficina, Código, Multimedia, Datos, Comprimidos, Sistema, Ejecutables, Desconocido. |
| **RF-08** | Sin extensión | Archivos sin extensión se clasifican como categoría `'Sin Extensión'` y se marcan para revisión de seguridad. |

### 7.3 Analyzer (RF-09 a RF-16)

| ID | Métrica | Descripción |
|---|---|---|
| **RF-09** | Distribución por categoría | Cantidad y volumen (bytes) total por cada categoría. Porcentaje sobre el total. |
| **RF-10** | Top N archivos pesados | Ranking de los N archivos de mayor tamaño (configurable, default 20). Incluye path, tamaño y categoría. |
| **RF-11** | Archivos inactivos | Archivos no modificados en más de X días (configurable, default 180). Agrupados por categoría. |
| **RF-12** | Archivos 0 bytes | Lista de archivos con tamaño cero. Indicador de archivos rotos o placeholders. |
| **RF-13** | Carpetas vacías | Listado de directorios sin archivos ni subdirectorios. Candidatos a limpieza. |
| **RF-14** | Duplicados por nombre | Archivos con el mismo nombre (ignorando ruta) que aparecen en 2+ ubicaciones. No implica mismo contenido. |
| **RF-15** | Timeline mensual | Distribución de archivos por mes/año de última modificación. Permite ver períodos de actividad. |
| **RF-16** | Análisis de permisos (Linux) | Detectar archivos con permisos `777`, world-writable (`o+w`), o SUID/SGID. Solo en Linux. |

---

## 8. Diccionario de Datos

### 8.1 FileRecord (contrato del Scanner)

Cada archivo escaneado produce un `FileRecord`. Esta es la estructura de datos central del sistema.

| Campo | Tipo Python | Fuente | Descripción |
|---|---|---|---|
| `path` | `Path` | `pathlib` | Ruta absoluta del archivo. |
| `name` | `str` | `path.name` | Nombre del archivo con extensión. |
| `extension` | `str` | `path.suffix` | Extensión en minúsculas. Vacío si no tiene. |
| `size_bytes` | `int` | `st_size` | Tamaño en bytes. 0 para archivos vacíos. |
| `mtime` | `datetime` | `st_mtime` | Fecha de última modificación del contenido. |
| `creation_time` | `datetime` | safe fn | Fecha de creación (OS-aware). Ver sección 5.3. |
| `atime` | `datetime` | `st_atime` | Fecha de último acceso (lectura). |
| `depth` | `int` | calculado | Nivel de profundidad relativo al path raíz del scan. |
| `is_hidden` | `bool` | OS-aware | `True` si el archivo está marcado como oculto. |
| `permissions` | `str \| None` | `st_mode` | Representación octal (ej: `'755'`). `None` en Windows. |
| `category` | `str` | Classifier | Categoría asignada por el Classifier. |
| `parent_dir` | `str` | `path.parent` | Directorio contenedor inmediato. |

### 8.2 Mapa de Categorías (categories.yaml)

| Categoría | Extensiones incluidas |
|---|---|
| **Oficina** | `.docx`, `.doc`, `.xlsx`, `.xls`, `.xlsm`, `.pptx`, `.ppt`, `.odt`, `.ods`, `.odp`, `.pdf`, `.rtf`, `.csv` |
| **Código** | `.py`, `.js`, `.ts`, `.java`, `.c`, `.cpp`, `.h`, `.cs`, `.go`, `.rs`, `.rb`, `.php`, `.sh`, `.bash`, `.sql`, `.html`, `.css`, `.json`, `.yaml`, `.toml`, `.xml`, `.md`, `.ipynb` |
| **Multimedia** | `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.svg`, `.mp4`, `.avi`, `.mkv`, `.mp3`, `.wav`, `.flac`, `.aac`, `.mov`, `.webm`, `.webp` |
| **Datos** | `.db`, `.sqlite`, `.sqlite3`, `.parquet`, `.arrow`, `.feather`, `.pickle`, `.pkl`, `.npy`, `.npz`, `.h5`, `.hdf5` |
| **Comprimidos** | `.zip`, `.tar`, `.gz`, `.bz2`, `.xz`, `.7z`, `.rar`, `.tar.gz`, `.tar.bz2` |
| **Ejecutables** | `.exe`, `.msi`, `.deb`, `.rpm`, `.appimage`, `.bat`, `.cmd`, `.ps1`, `.vbs` |
| **Sistema** | `.log`, `.ini`, `.cfg`, `.conf`, `.env`, `.lock`, `.tmp`, `.bak`, `.swp`, `.DS_Store`, `.lnk` |
| **Desconocido** | Cualquier extensión no mapeada en las categorías anteriores. |

---

## 9. Requerimientos No Funcionales

| ID | Atributo | Especificación |
|---|---|---|
| **RNF-01** | Performance | El scan de 100.000 archivos debe completarse en menos de 60 segundos en hardware estándar (SSD, 8GB RAM). |
| **RNF-02** | Compatibilidad OS | Funcionar sin cambios en Windows 10+, Ubuntu 20.04+, Debian 11+. Python 3.10+ como requisito mínimo. |
| **RNF-03** | Mantenibilidad | Cobertura de tests >= 80%. Type hints en todas las funciones públicas. Docstrings en todos los módulos. |
| **RNF-04** | Privacidad | Cero lectura de contenido de archivos. Los reportes no incluyen datos personales inferidos. |
| **RNF-05** | Extensibilidad | Agregar una nueva categoría debe requerir solo editar el YAML de configuración, sin tocar código Python. |
| **RNF-06** | Portabilidad | Cero dependencias de sistema externas en Fase 1. Solo `pip install`. No requiere Docker. |
| **RNF-07** | Logging | Producir `fsaudit.log` con nivel configurable (`DEBUG`/`INFO`/`WARNING`). Incluir timestamp, duración y conteos. |

---

## 10. Estructura del Reporte Excel

El reporte Excel es el output primario de FSAudit. Consta de las siguientes hojas:

| # | Hoja | Contenido |
|---|---|---|
| 1 | **Dashboard** | KPIs globales: total archivos, volumen total, archivos por categoría, top 5 directorios, alertas activas. |
| 2 | **Por Categoría** | Tabla: categoría, cantidad, bytes, % del total, promedio de tamaño, archivo más reciente, archivo más antiguo. |
| 3 | **Timeline** | Archivos agrupados por mes/año de modificación. Permite ver la curva de actividad histórica. |
| 4 | **Top Archivos Pesados** | Ranking Top 20 por tamaño. Columnas: nombre, ruta, tamaño (KB/MB), categoría, última modificación. |
| 5 | **Archivos Inactivos** | Archivos sin modificación en X días. Con columna 'días de inactividad' calculada. |
| 6 | **Alertas** | Archivos 0 bytes, sin extensión, ejecutables fuera de lugar, permisos inseguros (Linux), duplicados. |
| 7 | **Por Directorio** | Top directorios por volumen y cantidad de archivos. Profundidad promedio por rama. |
| 8 | **Inventario Completo** | Tabla con todos los `FileRecord`. Filtrable. Base para análisis ad-hoc en Excel. |

---

## 11. Variables para Escalabilidad del Análisis

Las siguientes variables amplían el análisis más allá del MVP y habilitan casos de uso avanzados. Organizadas por dimensión:

| Dimensión | Variable / Métrica | Valor analítico |
|---|---|---|
| **Productividad** | Archivos creados/semana | Detectar períodos de alta producción, estacionalidad del trabajo. |
| **Productividad** | Ratio modificación/creación | Archivos con alto ratio = trabajo iterativo (borradores). Ratio bajo = archivos 'terminados'. |
| **Productividad** | Hora del día de modificación | Distribución horaria de actividad. Identifica patrones de trabajo (mañana/tarde/noche). |
| **Organización** | Profundidad promedio del árbol | Alta profundidad = estructura compleja o desorganizada. Umbral recomendado: <= 5 niveles. |
| **Organización** | Archivos en raíz del usuario | Indicador directo de desorden digital. |
| **Almacenamiento** | Tasa de crecimiento (Fase 3) | Delta de volumen entre dos scans. Permite proyección de necesidad de almacenamiento futuro. |
| **Almacenamiento** | Distribución de tamaño (histograma) | Percentiles p50, p90, p99 de tamaño. Identifica outliers de almacenamiento. |
| **Seguridad** | Ejecutables en carpetas de datos | Alerta de seguridad: `.exe`/`.sh` en directorios de documentos o descargas. |
| **Seguridad** | Archivos con permisos world-write | Riesgo de seguridad en entornos multiusuario o servidores. |
| **Evolutiva** | Delta entre scans (Fase 3) | Archivos nuevos, eliminados y modificados entre dos snapshots. Base para auditoría temporal. |
| **Evolutiva** | Score de salud del filesystem | Índice compuesto: penaliza archivos 0 bytes, inactivos, carpetas vacías, desorganización. Rango: 0–100. |

---

## 12. Fases y Roadmap

| Fase | Nombre | Entregables | Criterio de Completitud |
|---|---|---|---|
| **Fase 1** | MVP Scanner | Scanner + Classifier + Analyzer base + Reporter Excel + CLI básica | Scan y reporte Excel funcional en Windows y Linux. Tests >= 80%. |
| **Fase 2** | Análisis Avanzado | Reporter HTML, detección de duplicados, análisis de permisos, score de salud, configuración YAML | Reporte HTML standalone generado. Score de salud calculado y documentado. |
| **Fase 3** | Histórico y Dashboard | Persistencia en SQLite, comparación entre scans, proyecciones, opcional: Dash dashboard | Delta entre dos scans visualizable. Proyección de crecimiento de almacenamiento. |

### 12.1 Estructura de Directorios del Proyecto

```
fsaudit/
├── cli.py                      # Punto de entrada
├── scanner/
│   ├── __init__.py
│   ├── scanner.py              # FileScanner class
│   ├── models.py               # FileRecord dataclass
│   └── platform_utils.py       # get_creation_time_safe(), is_hidden()
├── classifier/
│   ├── __init__.py
│   ├── classifier.py           # FileClassifier class
│   └── categories.yaml         # Mapa extensión → categoría
├── analyzer/
│   ├── __init__.py
│   ├── analyzer.py             # FileAnalyzer class
│   └── metrics.py              # AnalysisResult dataclass
├── reporter/
│   ├── __init__.py
│   ├── base.py                 # BaseReporter ABC
│   ├── excel_reporter.py
│   ├── html_reporter.py
│   ├── json_reporter.py
│   └── templates/
│       └── report.html.j2
├── tests/
│   ├── conftest.py
│   ├── test_scanner.py
│   ├── test_classifier.py
│   └── test_analyzer.py
├── config.yaml                 # Configuración global
├── requirements.txt
└── README.md
```

---

## 13. Riesgos y Mitigaciones

| Riesgo | Impacto | Mitigación |
|---|---|---|
| `ctime` incoherente en Linux (no es fecha de creación real) | Medio | Documentar explícitamente en el reporte. Usar `min(mtime, ctime)` como proxy. En Fase 3: explorar `statx()` para `crtime`. |
| `PermissionError` en directorios del sistema | Bajo | `try/except` en el Scanner. Archivos inaccesibles → log + contador en reporte. No detiene el scan. |
| Scan lento en filesystems muy grandes (>500k archivos) | Medio | Barra de progreso (`tqdm`). En Fase 2: paralelización con `ThreadPoolExecutor` para el `stat()`. |
| Symlinks circulares causan loop infinito | Alto | `os.walk(followlinks=False)` por defecto. Opción `--follow-symlinks` explícita con contador de ciclos. |
| Encoding de nombres de archivos con caracteres especiales | Medio | `pathlib` maneja UTF-8 nativamente. En Windows: uso de `os.fsdecode()` para rutas largas (>260 chars). |

---

*FSAudit v1.0 — PRD — Marzo 2026 — Documento interno*
