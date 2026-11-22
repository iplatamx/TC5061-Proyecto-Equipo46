"""Import the existing P1 versions into the Compose MLflow registry."""

import os
from pathlib import Path

import mlflow
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException

MODEL_NAME = os.getenv("MIBICI_MODEL_NAME", "mibici-equipo46-p1-demanda")
ARTIFACTS_ROOT = Path(os.getenv("MIBICI_LEGACY_MODELS_PATH", "/legacy-models"))
TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
REGISTRY_URI = os.getenv("MLFLOW_REGISTRY_URI", TRACKING_URI)
VERSIONS = {
    "1": "m-3e27185503b744b9a5b99834d74f85f3",
    "2": "m-48b9c4cf177c47d4a76376cc035ed5d9",
}


def main():
    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_registry_uri(REGISTRY_URI)
    client = MlflowClient(tracking_uri=TRACKING_URI, registry_uri=REGISTRY_URI)

    try:
        client.get_registered_model(MODEL_NAME)
    except MlflowException as exc:
        if exc.error_code not in {"RESOURCE_DOES_NOT_EXIST", "NOT_FOUND"}:
            raise
        client.create_registered_model(MODEL_NAME)

    registered = {
        str(version.version)
        for version in client.search_model_versions(f"name='{MODEL_NAME}'")
    }

    for expected_version, model_id in VERSIONS.items():
        if expected_version in registered:
            continue

        model_path = ARTIFACTS_ROOT / model_id / "artifacts"
        if not (model_path / "MLmodel").is_file() or not (model_path / "model.pkl").is_file():
            raise FileNotFoundError(f"No se encontraron los artefactos P1 en {model_path}")

        with mlflow.start_run(run_name=f"import-p1-v{expected_version}") as run:
            mlflow.set_tags(
                {
                    "legacy_source": "semana-07",
                    "legacy_model_id": model_id,
                    "legacy_model_version": expected_version,
                }
            )
            mlflow.log_artifacts(str(model_path), artifact_path="model")
            run_id = run.info.run_id

        created = client.create_model_version(
            name=MODEL_NAME,
            source=f"runs:/{run_id}/model",
            run_id=run_id,
            description=f"Importado de semana 7; versión P1 {expected_version}.",
        )
        if str(created.version) != expected_version:
            raise RuntimeError(
                f"Se esperaba la versión {expected_version}, pero MLflow creó {created.version}."
            )
        print(f"Registrado {MODEL_NAME} versión {created.version}")

    client.set_registered_model_alias(MODEL_NAME, "champion", "1")
    print(f"Alias champion -> {MODEL_NAME} versión 1")


if __name__ == "__main__":
    main()
