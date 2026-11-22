# Despliegue temporal en AWS

Esta guía despliega el stack existente de Docker Compose en una instancia EC2 de la región **US East (Ohio), `us-east-2`**. La plantilla no abre puertos de entrada: la API, MLflow y Locust quedan accesibles desde los contenedores y desde una sesión de administración de AWS Systems Manager. El modelo se copia desde un paquete privado en S3; no se publica en GitHub.

## Recursos que crea la plantilla

- Una instancia EC2 Linux `m7i-flex.large` (2 vCPU, 8 GiB RAM).
- Un volumen EBS gp3 cifrado de 30 GiB, que se elimina al terminar la instancia.
- Una IPv4 pública para que la instancia descargue imágenes y paquetes; el grupo de seguridad no permite tráfico entrante.
- Un bucket S3 privado para los dos paquetes y los reportes de Locust. Los objetos vencen en dos días.
- Un rol de instancia con Systems Manager y permisos de S3 limitados a leer `week10/` y escribir en `reports/`.

No incluye balanceador, NAT Gateway ni base de datos administrada. MLflow conserva su SQLite y artefactos en el volumen persistente de la instancia.

## Empaquetar el código y los modelos

Desde PowerShell, en cualquier carpeta, ejecuta:

```powershell
C:\IVAN\MNA\TC5061\semana-10\deploy\aws\package_aws.ps1
```

El script crea en `%TEMP%` dos archivos: `source.zip` con el commit de la rama AWS y `week07-models.zip` con los modelos que Compose importa desde Semana 7. Si los modelos están en otra ubicación:

```powershell
C:\IVAN\MNA\TC5061\semana-10\deploy\aws\package_aws.ps1 -ModelDirectory "C:\ruta\mlruns\2\models"
```

## Crear la infraestructura

1. En AWS Console, selecciona **US East (Ohio), `us-east-2`**.
2. Abre **CloudFormation → Create stack → With new resources (standard)**.
3. Carga `deploy/aws/stack.yaml` como plantilla.
4. Selecciona el VPC predeterminado y una subred pública dentro de ese VPC. Mantén `m7i-flex.large`.
5. Revisa la plantilla y crea el stack. La instancia empezará a generar cargos cuando quede en estado `CREATE_COMPLETE`.
6. En **Outputs**, copia `ArtifactBucketName`. En **S3**, abre ese bucket privado y sube ambos ZIP al prefijo `week10/`:
   - `week10/source.zip`
   - `week10/week07-models.zip`

La instancia revisa ese prefijo cada dos minutos. Cuando estén los dos objetos, los descarga, construye la imagen con Compose y levanta MLflow y la API. La primera construcción puede tardar varios minutos.

## Verificar y ejecutar Locust

En **EC2 → Instances → Connect → Session Manager**, selecciona la instancia y abre una sesión. Comprueba el despliegue:

```bash
sudo systemctl status week10-deploy.service
cd /opt/tc5061/semana-10
sudo docker compose ps
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:5000/health
```

Ejecuta la prueba y captura CPU/memoria desde la sesión de Systems Manager:

```bash
sudo bash /opt/tc5061/semana-10/deploy/aws/run_loadtest.sh
```

El script genera el reporte HTML/CSV y muestrea `docker stats` para API y MLflow cada dos segundos. Después sube los resultados al prefijo privado `reports/semana10/` del mismo bucket; puedes descargarlos desde la consola S3.

## Resultados y costos de referencia AWS

La ejecución del 22 de noviembre de 2026 en us-east-2 usó 20 usuarios de Locust, 5 usuarios nuevos por segundo y una duración de un minuto. El resultado final fue 2,305 solicitudes a /predict, cero fallos, throughput de 38.52 solicitudes/s, promedio de 6 ms, p95 de 11 ms y p99 de 17 ms. El reporte completo y las gráficas están en [reports/semana10/analisis_finops.md](../../reports/semana10/analisis_finops.md).

Durante 13 muestras tomadas en EC2, la API promedió 14.47 % de CPU y 183.1 MiB de memoria (máximo 36.88 % y 183.4 MiB); MLflow promedió 1.39 % de CPU y 628.0 MiB (máximo 8.01 % y 628.1 MiB).

La estimación usa como referencia USD $0.0958/h para EC2 m7i-flex.large en us-east-2, USD $0.005/h por IPv4 pública en uso y USD $0.08/GiB-mes para gp3. Con un disco de 30 GiB, el costo base aproximado es USD $0.10409/h:

| Tiempo encendido | Costo base | Presupuesto con margen de 16 % |
|---|---:|---:|
| 24 horas | MXN $47.53 | MXN $55.14 |
| 730 horas | MXN $1,445.75 | MXN $1,677.07 |

La conversión usa MXN $19.027/USD, publicado por DOF/Banxico el 20 de noviembre de 2026. Al throughput observado, el costo estimado es USD $0.75 (MXN $14.28) por millón de inferencias, distribuyendo EC2, IPv4 y EBS entre 138,672 inferencias por hora. Es una proyección de capacidad sostenida, no el importe facturado del ejercicio. No incluye impuestos, S3, transferencia de datos ni descuentos de cuenta. Revisa el importe real en Cost Explorer. Referencias: [AWS EC2 On-Demand](https://aws.amazon.com/ec2/pricing/on-demand/), [precio de IPv4](https://aws.amazon.com/vpc/pricing/), [precio gp3](https://aws.amazon.com/ebs/pricing/) y [tipo de cambio DOF/Banxico](https://www.banxico.org.mx/tipcamb/tipCamMIAction.do).

Al terminar:

1. Descarga desde S3 los reportes que quieras conservar.
2. En S3, elimina los objetos del bucket de este stack. La plantilla no puede borrar un bucket que todavía contiene objetos.
3. En CloudFormation, elimina el stack; esto termina EC2, elimina el volumen y borra el bucket vacío.
4. Confirma en EC2 que no haya instancias ni volúmenes asociados en ejecución.

`docker compose down` solo detiene los contenedores; la instancia EC2 continúa facturándose. La API no queda publicada a Internet. Si se requiere una URL pública, primero hay que decidir el rango de IP permitido y configurar HTTPS y autenticación.
