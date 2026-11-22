# Semana 10 — Prueba de carga y análisis FinOps

## Escenario

- Fecha: 22 de noviembre de 2026.
- Locust 2.47.0, ejecutado como contenedor del perfil loadtest.
- 20 usuarios concurrentes, 5 usuarios nuevos por segundo y 60 segundos de carga.
- Cada usuario envía POST /predict con las ocho variables del contrato P1 y espera entre 0.2 y 0.8 segundos.
- API y MLflow se ejecutaron con Docker Compose en Docker Desktop. El generador Locust compartió el mismo host Docker, por lo que los resultados describen este entorno local.

## Desempeño

El [reporte HTML de Locust](locust_report.html) incluye gráficas de tiempo de respuesta, peticiones por segundo y fallos. Los CSV se conservan como datos complementarios.

| Métrica | Resultado del resumen HTML |
|---|---:|
| Peticiones | 2,096 |
| Errores | 0 (0 %) |
| Latencia promedio | 41.82 ms |
| Mediana | 34 ms |
| Latencia p95 | 79 ms |
| Latencia máxima | 2,037 ms |
| Throughput | 32.30 req/s |

Se observó una latencia máxima aislada de aproximadamente 2.04 s; por eso el p95 (79 ms) es más representativo del comportamiento habitual que el máximo.

**Diferencia entre archivos:** el resumen final del HTML registra 2,096 peticiones, mientras que el resumen y la última muestra del CSV de Locust registran 2,082, ambos con cero fallos. Se usa el resumen HTML como fuente del conteo final y del throughput; se conserva el CSV como serie temporal, dejando documentada la diferencia de 14 peticiones (0.67 %).

## Consumo de recursos

La captura de [docker_stats.csv](docker_stats.csv) contiene 11 muestras por contenedor durante la ventana de carga.

| Contenedor | CPU promedio | CPU máxima | Memoria promedio | Memoria máxima |
|---|---:|---:|---:|---:|
| API | 125.11 % | 172.16 % | 261.7 MiB | 273.7 MiB |
| MLflow | 0.98 % | 1.09 % | 657.4 MiB | 657.5 MiB |

Docker reporta CPU por contenedor y el porcentaje puede superar 100 % cuando el proceso usa más de un núcleo. La API fue la parte intensiva en CPU durante esta prueba; MLflow mantuvo principalmente el registro y sirvió artefactos al iniciar la API.

## Estimación FinOps

Como referencia se usa una instancia AWS EC2 c6i.xlarge bajo demanda en us-east-1: 4 vCPU, 8 GiB de memoria y USD $0.17 por hora, según [AWS Prescriptive Guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/optimize-costs-microsoft-workloads/right-size-selection.html).

Con el throughput del resumen HTML:

- Inferencias teóricas por hora: 32.2999 req/s × 3,600 = **116,280**.
- Costo estimado: USD $0.17 ÷ 116,280 = **USD $0.00000146 por inferencia**.
- Equivalente: aproximadamente **USD $1.46 por millón de inferencias**.
- Si la instancia permanece encendida 730 horas al mes: **USD $124.10/mes**, antes de almacenamiento, transferencia, impuestos y otros servicios.

Es una estimación ilustrativa: supone que una instancia c6i.xlarge sostendría el throughput medido localmente. No se ejecutó una prueba en AWS, así que no se debe interpretar como una cotización ni como capacidad garantizada. El costo fijo mensual domina con tráfico bajo; con carga sostenida, el costo unitario depende directamente del throughput real.

## Acciones de optimización

1. Ajustar CPU, memoria y número de procesos a partir de pruebas repetidas en la instancia de destino; no dimensionar la nube solo con la medición de Docker Desktop.
2. Escalar réplicas de API durante picos y reducirlas en periodos de poco tráfico; revisar el punto de equilibrio frente a una instancia fija 24/7.
3. Mantener el modelo en memoria en FastAPI, como hace esta implementación, para evitar consultar el Registry en cada predicción.
4. Probar el generador de carga desde otro host para separar el consumo de Locust del consumo del servicio.
5. Comparar procesamiento por lotes y alternativas de CPU solo después de validar la misma calidad del modelo y el contrato P1.

## Archivos de evidencia

- [Gráficas y resumen HTML](locust_report.html)
- [Resumen CSV de Locust](locust_stats_stats.csv)
- [Serie temporal CSV de Locust](locust_stats_stats_history.csv)
- [Muestras CPU/memoria](docker_stats.csv)
