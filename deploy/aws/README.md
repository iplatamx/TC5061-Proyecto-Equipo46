# Despliegue temporal en AWS

Esta guía despliega el stack existente de Docker Compose en una instancia EC2 de la región **US East (Ohio), `us-east-2`**. La plantilla no abre puertos de entrada: la API, MLflow y Locust quedan accesibles desde los contenedores y desde una sesión de administración de AWS Systems Manager. El modelo se copia desde un paquete privado en S3; no se publica en GitHub.

## Recursos que crea la plantilla

- Una instancia EC2 Linux `t3.medium` (2 vCPU, 4 GiB RAM).
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
4. Selecciona el VPC predeterminado y una subred pública dentro de ese VPC. Mantén `t3.medium`.
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

## Costos de referencia y apagado

El tamaño se ajustó a la medición local: los contenedores de API y MLflow consumieron cerca de 920 MiB combinados y la API promedió 125 % de CPU durante una prueba breve. `t3.medium` tiene 2 vCPU y 4 GiB; sus créditos de CPU pueden generar un cargo adicional si se mantiene uso alto durante mucho tiempo.

Con las tarifas de referencia de **USD $0.0418/h** para `t3.medium`, **USD $0.005/h** por IPv4 pública y **USD $0.08/GiB-mes** para gp3, el cálculo aproximado es:

| Tiempo encendido | Antes de impuestos | Con margen de 16 % |
|---|---:|---:|
| 24 horas | MXN $23 | MXN $27 (presupuesta $30) |
| 730 horas | MXN $696 | MXN $807 (presupuesta $850) |

La conversión usa MXN $19.027/USD (DOF, 20 de noviembre de 2026). Es una referencia con precios de lista; la región, impuestos, créditos de CPU y uso de red pueden cambiar la factura. [Tarifa EC2 T3](https://aws.amazon.com/ec2/instance-types/t3/), [precio de IPv4](https://aws.amazon.com/vpc/pricing/), [precio gp3](https://aws.amazon.com/ebs/pricing/), [tipo de cambio DOF](https://dof.gob.mx/indicadores_detalle.php?cod_tipo_indicador=158&dfecha=20%2F11%2F2026&hfecha=20%2F11%2F2026).

Al terminar:

1. Descarga desde S3 los reportes que quieras conservar.
2. En S3, elimina los objetos del bucket de este stack. La plantilla no puede borrar un bucket que todavía contiene objetos.
3. En CloudFormation, elimina el stack; esto termina EC2, elimina el volumen y borra el bucket vacío.
4. Confirma en EC2 que no haya instancias ni volúmenes asociados en ejecución.

`docker compose down` solo detiene los contenedores; la instancia EC2 continúa facturándose. La API no queda publicada a Internet. Si se requiere una URL pública, primero hay que decidir el rango de IP permitido y configurar HTTPS y autenticación.
