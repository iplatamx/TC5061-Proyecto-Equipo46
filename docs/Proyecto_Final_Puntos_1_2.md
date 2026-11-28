# Actividad 11 — Proyecto integrador MiBici | Equipo 46
**Responsable de los puntos 1 y 2:** Axel Fernando Rábago Díaz.  
**Ejecución documentada:** 27 de noviembre de 2026.  
**Alcance:** 35 puntos de la rúbrica; experimentación y Model Registry. No certifica por sí solo la API, CI/CD, Locust, monitoreo, FinOps ni la entrega audiovisual.

## 1. Estructura y experimentación (20 puntos)

El repositorio conserva la separación modular de Cookiecutter Data Science. P1 estima salidas de bicicletas por estación en la siguiente hora; P2 clasifica un indicador indirecto de presión operacional, no disponibilidad real de bicicletas; P3 agrupa estaciones según perfiles de uso.

| Componente | Ubicación | Función |
|---|---|---|
| Ingesta y datos | `mibici/dataset.py`, `data/manifest/` | Limpieza, Parquet, hashes |
| Configuración | `mibici/config.py`, `configs/` | Parámetros, rutas y semilla |
| Feature engineering | `mibici/features.py` | Panel temporal, ventanas móviles y perfiles |
| Experimentación | `mibici/modeling/`, `MLproject` | Baselines y búsqueda de candidatos |
| Entorno | `python_env.yaml`, `requirements.txt`, `pyproject.toml` | Python 3.11.9, MLflow 3.6.0, scikit-learn 1.7.2, cloudpickle 3.1.2 |
| Calidad | `tests/`, `pytest.ini` | Pruebas unitarias e integración |
| Serving y operación | `api/`, `mibici/serving/`, `ops/`, `docker-compose.yml`, `.github/`, `loadtest/` | Servicio P1, orquestación y automatización |
| Evidencias | `docs/evidencias_final/` | Auditorías, hashes y pruebas |

### Datos y reproducibilidad

Se recuperaron los Parquet originales de enero a septiembre de 2026. Los diez archivos coincidieron mediante SHA-256 con el manifiesto histórico `129a4a57efc7`; los nueve archivos de viajes coincidieron también con `d038fe16493d`, pero `stations.parquet` no. Se conservaron los dos manifiestos sin alterar los hashes.

| Versión | Viajes | Estaciones | Uso |
|---|---:|---:|---|
| `129a4a57efc7` | 3,361,307 | 470 | Experimentos finales auditados |
| `d038fe16493d` | 3,361,307 | 484 | Ingesta documentada anteriormente en el repositorio |

Copias: [470 estaciones](evidencias_final/manifests/data_manifest_129a4a57efc7.json) y [484 estaciones](evidencias_final/manifests/data_manifest_d038fe16493d.json). La diferencia en el archivo de estaciones está comprobada; no se comprobó exhaustivamente su causa. El manifiesto activo de la rama de entrenamiento es el de 470 estaciones; debe revisarse con el equipo antes de fusionar, por su impacto potencial sobre la preparación de monitoreo y otros procesos. Los Parquet, CSV, pesos y bases locales no se publican en Git.

P1 utiliza ocho variables: `station_id`, salidas y llegadas de la hora observada, medias móviles de salidas de 24 y 168 horas y tres variables de calendario. P2 añade capacidad de la estación. P3 utiliza 336 características de llegadas y salidas por día de la semana y hora, con StandardScaler y KMeans. P1 y P2 se dividen cronológicamente en 70/15/15 por tiempo objetivo; la elección usa validación. P3 usa métricas internas de agrupación y no tiene particiones de prueba supervisada.

### Procedimiento de reproducción (PowerShell)

Desde un clon separado del que conserva el despliegue. Si el PR no se ha fusionado, obtener la rama correspondiente. Para reproducir exactamente los resultados auditados, usar el commit `c0e339c64045f660ce554e40cba05c7802231a56` una vez disponible en GitHub.

```powershell
git clone https://github.com/iplatamx/TC5061-Proyecto-Equipo46.git MiBici-reproduccion
cd MiBici-reproduccion
# Si la rama final aún no está fusionada:
# git fetch https://github.com/axelR07/TC5061-Proyecto-Equipo46.git feature/actividad11-puntos1-2-axel
# git switch --detach FETCH_HEAD
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python --version
python -m pip install -r requirements.txt
python -m pip install -e .
python -m pip install pytest==9.2.0
python -m pip check
```

Terminal 1: servidor aislado de experimentación; no utilizar el puerto de Compose. Ejecutar en la raíz del clon, con el entorno activo.

```powershell
python -m mlflow server --backend-store-uri sqlite:///mlflow_repro.db --artifacts-destination ./mlartifacts --host 127.0.0.1 --port 5002 --workers 1
```

Terminal 2: conectar al mismo servidor.

```powershell
.\.venv\Scripts\Activate.ps1
$env:MLFLOW_TRACKING_URI = 'http://127.0.0.1:5002'
$env:MLFLOW_REGISTRY_URI = $env:MLFLOW_TRACKING_URI
$env:MLFLOW_EXPERIMENT_NAME = 'mibici-equipo46'
```

**Ruta A — reproducción exacta de los datos auditados:** obtener del equipo una copia de los diez Parquet históricos verificados (no incluidos en Git), colocarlos en `data/processed/` y copiar el manifiesto de 470 estaciones a `data/manifest/data_manifest.json`. El siguiente bloque valida exclusivamente los archivos procesados; no requiere los CSV originales.

```powershell
Copy-Item docs/evidencias_final/manifests/data_manifest_129a4a57efc7.json data/manifest/data_manifest.json -Force
@'
import json, hashlib
from pathlib import Path
m = json.loads(Path("data/manifest/data_manifest.json").read_text(encoding="utf-8-sig"))
assert m["data_version"] == "129a4a57efc7" and m["complete"] is True
assert len(m["files"]) == 10
for item in m["files"]:
    p = Path("data/processed") / item["name"]
    with p.open("rb") as f:
        assert hashlib.file_digest(f, "sha256").hexdigest() == item["sha256"], str(p)
    print("PASS:", p.name)
print("PASS: 10/10")
'@ | python -
```

**Ruta B — ingesta nueva desde fuentes públicas:** si no se dispone de la copia histórica, ejecutar en un clon separado:

```powershell
mlflow run . -e ingest --env-manager local --experiment-name mibici-equipo46
python -m mibici.dataset --verify
```

La ingesta nueva no fue ejecutada en la sesión final: se reutilizaron Parquet verificados. La ruta B puede producir una versión diferente si cambian los archivos fuente; no se garantiza identidad exacta de resultados. No sustituir hashes manualmente. Si el equipo desea garantizar reproducibilidad exacta por terceros, debe proporcionar acceso al snapshot histórico autorizado o a los CSV originales correspondientes y verificar sus hashes.

Una vez comprobados los datos, ejecutar secuencialmente los cuatro entry points probados el 27 de noviembre:

```powershell
mlflow run . -e train -P question=P1 -P model=dummy_regressor --env-manager local --experiment-name mibici-equipo46
mlflow run . -e search_p1 --env-manager local --experiment-name mibici-equipo46
mlflow run . -e search_p2 --env-manager local --experiment-name mibici-equipo46
mlflow run . -e search_p3 --env-manager local --experiment-name mibici-equipo46
```

Se obtuvieron 14 runs FINISHED: un baseline P1, tres runs de búsqueda y diez candidatos (3 P1, 3 P2, 4 P3). Los baselines independientes P2 y P3 no se ejecutaron en esta sesión; K=3 sí se entrenó dentro de `search_p3`. El run padre de P3 no guarda métricas ni parámetros agregados; los cuatro hijos conservan los resultados. Las advertencias Deepchecks no detuvieron el entrenamiento P3, pero no equivalen a aprobar todas las reglas de calidad.

## 2. Modelo y Registry (15 puntos)

### Resultados experimentales de la Actividad 11

| P1 | MAE validación | RMSE validación | R² validación | MAE prueba |
|---|---:|---:|---:|---:|
| DummyRegressor | 1.310377 | 2.278812 | -0.000904 | 1.475630 |
| P1-HGB-01 | 0.749757 | 1.351632 | 0.647879 | 0.869277 |
| **P1-HGB-02** | **0.735193** | **1.307012** | **0.670743** | **0.854278** |
| P1-HGB-03 | 0.736188 | 1.308476 | 0.670006 | 0.855044 |

El baseline y los tres candidatos P1 reprodujeron las métricas históricas registradas. El MAE de validación disminuyó aproximadamente 43.89% frente al baseline; el MAE de prueba, 42.11%. Semilla 42. Partición P1: 2,160,006 / 462,993 / 462,993 filas.

| P2 | F1 validación | Recall validación | Balanced Accuracy | F1 prueba |
|---|---:|---:|---:|---:|
| P2-HGB-01 | 0.485343 | 0.854702 | 0.775886 | 0.494196 |
| **P2-HGB-02** | **0.488584** | 0.859748 | 0.779114 | **0.497353** |
| P2-HGB-03 | 0.488387 | 0.860435 | 0.779135 | 0.496755 |

El criterio primario es F1, con recall y balanced accuracy como desempates. P2-HGB-02 tiene recall elevado (85.97%) y precisión de 34.13% en validación: los falsos positivos limitan su uso como alerta automática. P1 y P2 seleccionados usan 100 iteraciones, learning rate 0.08 y 31 hojas máximas.

| P3 | Silhouette | Calinski-Harabasz |
|---|---:|---:|
| **K=3** | **0.450625** | **263.931303** |
| K=4 | 0.379058 | 232.765159 |
| K=5 | 0.363824 | 200.893706 |
| K=6 | 0.340338 | 175.381720 |

K=3 maximiza ambos criterios seleccionados; los grupos contienen 315, 146 y 9 estaciones. La inercia no es el criterio primario porque tiende a disminuir al aumentar K. Se añadió K=3 a la búsqueda para evaluar todas las configuraciones en una misma ejecución.

### Registro y auditoría

En el servidor aislado de experimentación (`5002`), ejecutar:

```powershell
python -m mibici.modeling.registry
python scripts/audit_final_registry.py --output docs/evidencias_final/registry_repro.json
python -m mibici.serving.verify_model
$env:RUN_MLFLOW_INTEGRATION = '1'
python -m pytest -q
```

`registry.py` selecciona por versión de datos del manifiesto vigente y criterios de ranking; carga los artefactos antes de registrar, crea o reutiliza versiones y asigna el alias `champion`. El registro cambia alias en el servidor indicado: no ejecutarlo contra el Registry de Compose o el histórico para reproducir esta sesión.

| Modelo registrado | Run ID de entrenamiento final | Selección |
|---|---|---|
| `mibici-equipo46-p1-demanda` | `0610d950317245e48f2f37b18db3a324` | P1-HGB-02 |
| `mibici-equipo46-p2-riesgo` | `8d0377015cc14b8baa52ef86fb42eafe` | P2-HGB-02 |
| `mibici-equipo46-p3-grupos` | `412c05f247a547ba8939204208bc7d2f` | KMeans K=3 |

Los tres: versión 1, `READY`, `champion`, `validation_status=approved`, entorno académico, datos `129a4a57efc7` y commit de entrenamiento `c0e339c64045f660ce554e40cba05c7802231a56`. La auditoría integral registró PASS sin errores ni avisos; el código rastreado estaba limpio al ejecutar la auditoría. Los números de versión y Run ID son locales a cada Registry. La API consume solo P1; P2 y P3 son modelos de análisis registrados, no endpoints desplegados.

### Consistencia con operación y gobernanza

| Puerto | Función | Evidencia |
|---|---|---|
| 5000 | MLflow de Docker Compose | P1 importado desde exportación; no contiene todo el linaje histórico |
| 5001 | Registry histórico recuperado | P1 auditado PASS; manifiesto histórico recuperado |
| 5002 | Registry final de experimentación | P1, P2, P3 auditados PASS |

El archivo `model.pkl` de P1 obtuvo el mismo SHA-256 en los tres entornos. Los tres devolvieron `3.923333879487776` para la entrada de referencia. La comparación certifica ese archivo serializado, no la identidad de todos los metadatos ni la respuesta de un servicio HTTP.

Para preparar Compose desde un clon que ya registró el P1 real en el puerto 5002 (sin necesidad de recuperar el Registry histórico), consultar el procedimiento de exportación de Semana 10 y ejecutar:

```powershell
$env:MLFLOW_TRACKING_URI = 'http://127.0.0.1:5002'
$env:MLFLOW_REGISTRY_URI = $env:MLFLOW_TRACKING_URI
python -m ops.export_champion
```

La exportación debe estar en `models/compose-champion/`. Si ya existe, revisar su origen antes de reemplazarla; no sobrescribir ni borrar un volumen activo sin coordinación. En un entorno limpio y con Docker disponible, validar Compose, iniciar los servicios y ejecutar el smoke test según el README. El servidor de experimentación 5002 puede continuar activo mientras Compose utiliza 5000. `ops/seed_registry.py` importa el modelo, valida firma/predicción y registra su propia versión; su run de importación no sustituye al run de entrenamiento. El CI utiliza un modelo sintético exclusivamente para smoke tests. Para el video usar el modelo real y una petición HTTP.

La evaluación offline de octubre documentada en Semana 9 recomienda challenger v2, pero no lo promueve automáticamente. Se conserva P1 v1 para la demo local: la identidad binaria está verificada. La comparación A/B de octubre es una ventana diferente y su conclusión debe coordinarse con el Model Card. No se afirma que v2 esté presente en el Registry final de 5002.

## 3. Evidencias y límites de aceptación

| Archivo | Resultado |
|---|---|
| [registry_audit.json](evidencias_final/registry_audit.json) | Diagnóstico inicial del Registry de Compose: FAIL por falta de linaje/otros modelos; no representa el Registry final |
| [registry_p1_historico.json](evidencias_final/registry_p1_historico.json) | PASS histórico P1, aviso por diferencia de manifiesto |
| [registry_final_integral.json](evidencias_final/registry_final_integral.json) | PASS integral, 3 modelos, sin errores ni avisos |
| [model_identity_sha256.json](evidencias_final/model_identity_sha256.json) | Los tres archivos `model.pkl` de P1 idénticos |
| [pytest_final.txt](evidencias_final/pytest_final.txt) | 64 passed, 3 warnings, 7.84 s; prueba de integración habilitada |

Las advertencias de Pytest son deprecaciones de Starlette y Typer; el resultado no expresa cobertura del 100% del código ni ausencia de vulnerabilidades. El README conserva los hallazgos históricos de seguridad para seguimiento. No publicar datos, pesos, bases SQLite, secretos o rutas privadas innecesarias. Revisar los manifiestos y JSON antes de subirlos. Pendientes de integración del equipo: acuerdo sobre manifiesto activo, coherencia del Model Card y A/B, acceso al snapshot histórico para terceros, PR revisado, Actions de la revisión final y demo HTTP con el stack real. La ingesta fresca, publicación remota y ejecución de CI/CD final no se certifican con esta auditoría.

Fuentes: repositorio MiBici Equipo 46, rúbrica Actividad 11, salidas de entrenamiento y auditorías del 27 de noviembre de 2026, y documentación de las semanas 6 a 10.
