# Model Card — Predicción de demanda MiBici (P1)

**Equipo:** 46  
**Fecha de revisión:** 27 de noviembre de 2026  
**Estado:** prototipo académico; las métricas provienen de evaluaciones retrospectivas.

## Resumen del modelo

| Campo | Descripción |
|---|---|
| Problema | Estimar cuántos viajes iniciarán en una estación MiBici durante la siguiente hora. |
| Nombre en MLflow Registry | `mibici-equipo46-p1-demanda` |
| Champion documentado | Versión 1, alias `champion`, candidato `P1-HGB-02`. |
| Algoritmo | `HistGradientBoostingRegressor` de scikit-learn. |
| Challenger evaluado | Versión 2, candidato `P1-HGB-02-week9-october-retrained`; no está promovido al alias `champion`. |
| Salida | Predicción numérica no negativa de viajes por estación-hora. |

La API resuelve el alias al arrancar y conserva la versión concreta durante ese
proceso. Debe verificarse el alias en MLflow antes de cada demostración o
despliegue; este documento refleja el estado guardado en la evidencia del
proyecto, no una consulta en vivo al Registry.

## Uso previsto y límites

El modelo sirve como apoyo para explorar la demanda agregada por estación y
hora, y para orientar la revisión operativa. Las predicciones requieren
supervisión humana y no deben activar por sí solas el traslado de bicicletas,
la asignación de personal ni decisiones que afecten a una persona.

No es una predicción individual ni estima la disponibilidad física de
bicicletas o anclajes. No reemplaza los modelos P2 (riesgo) o P3 (agrupamiento),
ni identifica causas de los cambios de demanda.

## Datos y variables

El entrenamiento P1 usa viajes abiertos de MiBici transformados a una tabla
estación-hora. El proyecto registra ingesta, hashes y versiones de datos en
`data/manifest/data_manifest.json`; las particiones temporales del experimento
P1 se separan cronológicamente en entrenamiento, validación y prueba (70/15/15).
Los candidatos se seleccionan por MAE de validación. La evidencia de drift y la
evaluación del challenger usan periodos posteriores y se describen aparte; no
deben confundirse con el conjunto original de prueba.

El contrato del modelo contiene ocho variables:

1. `station_id`
2. `departures_this_hour`
3. `arrivals_this_hour`
4. `departures_mean_last_24h`
5. `departures_mean_last_168h`
6. `target_hour`
7. `target_dayofweek`
8. `target_is_weekend`

El objetivo es `target_departures_next_hour`. La salida se limita a cero o más.
El contrato excluye el identificador de usuario, género y año de nacimiento;
las variables móviles deben estar calculadas con información disponible hasta
la hora observada, sin incorporar el objetivo futuro.

## Evaluación

El champion y el challenger se evaluaron sobre las mismas 181,632 observaciones
de la ventana temporal del 16 al 31 de octubre de 2026:

| Métrica | Champion v1 (`P1-HGB-02`) | Challenger v2 |
|---|---:|---:|
| MAE (menor es mejor) | 1.0257 | **1.0179** |
| RMSE (menor es mejor) | 1.7848 | **1.7527** |
| R² (mayor es mejor) | 0.7071 | **0.7175** |
| Sesgo medio (predicción − real) | −0.0477 | −0.0322 |
| Tasa de subestimación | 32.26% | 32.14% |

El challenger redujo MAE aproximadamente 0.76% y mejoró las otras métricas en
esa evaluación. El alias `champion` se mantuvo en la versión 1; la evaluación
no produjo promoción automática. La comparación es retrospectiva sobre un
holdout común, no un A/B test aleatorizado con tráfico en vivo.

## Monitoreo y cambio de distribución

El reporte retrospectivo de Evidently comparó el periodo de referencia de
entrenamiento (1 de enero–11 de julio de 2026, 2,169,178 filas) con octubre de
2026 (351,439 filas). Detectó drift en 4 de 8 variables de entrada: conteos de
salidas/llegadas y medias móviles de 24/168 horas. El reporte registró cero
faltantes y cero filas duplicadas en octubre.

El drift estadístico señala un cambio en las entradas; por sí solo no demuestra
que el error del modelo haya aumentado. Se debe contrastar con etiquetas nuevas
y métricas predictivas antes de cambiar el modelo. Actualmente el reporte es
retrospectivo: no es una alerta conectada a tráfico en tiempo real.

## Consideraciones, riesgos y mitigaciones

- **Subestimación:** cerca de 32% de las predicciones de ambos modelos quedó
  por debajo del valor observado en el holdout. Revisar este error por
  estación, hora y periodo antes de usar las estimaciones en planificación.
- **Variables externas:** eventos, clima, obras, interrupciones y cambios de
  servicio no están incluidos; pueden causar cambios que el modelo no anticipe.
- **Cobertura:** el desempeño por estación y por subgrupo no está documentado
  en las evidencias disponibles; no asumir que es uniforme.
- **Privacidad:** la inferencia utiliza agregados por estación-hora y no recibe
  identificadores de usuarios ni atributos demográficos.
- **Incertidumbre:** la API devuelve una estimación puntual, no un intervalo de
  predicción ni una garantía de demanda.
- **Gobernanza:** el challenger no se promueve automáticamente. La versión y
  sus métricas deben revisarse y aprobarse antes de mover el alias.

## Operación y artefactos del proyecto

- [Contrato y validación de entradas](../mibici/serving/contract.py)
- [API FastAPI](../api/main.py) y [Docker Compose](../docker-compose.yml)
- [Workflow CI/CD y smoke test de Locust](../.github/workflows/semana10-ci.yml)
- [Reporte de drift con Evidently](evidencias_semana9/evidently_drift_october_2026.html)
- [Resultado y métricas del A/B retrospectivo](evidencias_semana9/ab_test_october_second_half.md)
- [Estimación FinOps por escenario](../reports/semana10_locust/finops_costo_inferencia.csv)
- [Escenario Locust](../loadtest/locustfile.py) y [resultados de carga](../reports/semana10_locust/)

La estimación FinOps es una comparación de costo basada en tarifas de
referencia y throughput medido; no representa un cargo de nube observado. El
workflow usa un modelo sintético en su smoke test para validar la integración y
no publica los pesos entrenados.
