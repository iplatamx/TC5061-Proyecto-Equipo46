"""Auditoría de solo lectura del Tracking y Registry ORIGINAL de MiBici.

Ejecutar desde la raíz: python scripts/audit_final_registry.py
No registra, promueve, entrena ni elimina modelos.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

MODELS = {
    'P1': ('mibici-equipo46-p1-demanda', {'P1-HGB-01', 'P1-HGB-02', 'P1-HGB-03'}, ('validation_mae',), False),
    'P2': ('mibici-equipo46-p2-riesgo', {'P2-HGB-01', 'P2-HGB-02', 'P2-HGB-03'}, ('validation_f1', 'validation_recall', 'validation_balanced_accuracy'), True),
    'P3': ('mibici-equipo46-p3-grupos', {f'P3_kmeans_{k}_station_usage_profiles' for k in (3, 4, 5, 6)}, ('silhouette', 'calinski_harabasz'), True),
}


def data_version(run):
    return run.data.tags.get('data_version') or run.data.params.get('data_version')


def rank_candidates(runs, names, metrics, maximize, version):
    rows = []
    for run in runs:
        name = run.data.tags.get('mlflow.runName')
        vals = run.data.metrics
        if (run.info.status == 'FINISHED' and name in names and data_version(run) == version
                and run.data.tags.get('logged_model_uri')
                and all(key in vals and math.isfinite(vals[key]) for key in metrics)):
            rows.append({'name': name, 'run_id': run.info.run_id,
                         'metrics': {key: vals[key] for key in metrics}})
    # La política de desempate no afecta la comparación de métricas equivalentes.
    return sorted(rows, key=lambda row: tuple(row['metrics'][key] for key in metrics), reverse=maximize)


def require(condition, message, errors):
    if not condition:
        errors.append(message)


def audit_model(client, mlflow, question, local_version):
    name, candidates, metrics, maximize = MODELS[question]
    errors, warnings = [], []
    report = {'question': question, 'name': name, 'alias': 'champion', 'errors': errors, 'warnings': warnings}
    try:
        registered = client.get_registered_model(name)
        report['aliases'] = dict(registered.aliases or {})
        version = client.get_model_version_by_alias(name, 'champion')
        tags = dict(version.tags or {})
        run_id = tags.get('source_run_id') or version.run_id
        report.update(version=str(version.version), status=str(version.status), run_id=run_id,
                      data_version=tags.get('data_version'), selected_run=tags.get('selected_run_name'),
                      source_model_uri=tags.get('source_model_uri'), validation_status=tags.get('validation_status'))
        require(str(version.status) == 'READY', 'Versión no está READY.', errors)
        require(bool(run_id), 'Falta Run ID de origen.', errors)
        require(tags.get('validation_status') == 'approved', 'Falta etiqueta validation_status=approved.', errors)
        require(bool(tags.get('source_model_uri')), 'Falta etiqueta source_model_uri.', errors)
        if not run_id:
            return report
        if version.run_id:
            require(version.run_id == run_id, 'Run ID de versión y etiqueta no coinciden.', errors)
        run = client.get_run(run_id)
        cohort = data_version(run)
        report.update(data_version=cohort, run_name=run.data.tags.get('mlflow.runName'),
                      run_status=run.info.status, experiment_id=run.info.experiment_id,
                      git_commit=run.data.tags.get('git_commit') or run.data.tags.get('mlflow.source.git.commit'),
                      params=dict(run.data.params), metrics={k:v for k,v in run.data.metrics.items() if math.isfinite(v)})
        require(run.info.status == 'FINISHED', 'Run de origen no finalizó correctamente.', errors)
        require(bool(cohort) and tags.get('data_version') == cohort, 'Versión de datos ausente o inconsistente.', errors)
        require(tags.get('source_model_uri') == run.data.tags.get('logged_model_uri'), 'URI registrada y URI del run no coinciden.', errors)
        require(tags.get('selected_run_name') == report['run_name'], 'Nombre del candidato no coincide con el run.', errors)
        if not report['git_commit'] or report['git_commit'] == 'unknown':
            warnings.append('No consta commit de entrenamiento verificable; revisar metadatos históricos.')
        if cohort != local_version:
            warnings.append('El manifiesto de trabajo difiere del histórico; se verifica el manifiesto del run, no se sustituye su hash.')
        # El manifiesto de entrenamiento debe ser recuperable del run de origen.
        try:
            with tempfile.TemporaryDirectory() as tmp:
                artifact = client.download_artifacts(run_id, 'data/data_manifest.json', tmp)
                manifest = json.loads(Path(artifact).read_text(encoding='utf-8'))
                report['run_manifest'] = {k: manifest.get(k) for k in ('data_version','start_month','end_month','complete','n_trips','n_stations')}
                require(manifest.get('complete') is True and manifest.get('data_version') == cohort,
                        'Manifiesto histórico incompleto o diferente del run.', errors)
        except Exception as exc:
            errors.append(f'No se recuperó data/data_manifest.json: {type(exc).__name__}. Revisar artefactos originales.')
        # Comparar exclusivamente candidatos con misma versión de datos.
        all_runs = []
        token = None
        while True:
            page = client.search_runs([run.info.experiment_id], filter_string="attributes.status = 'FINISHED'", max_results=1000, page_token=token)
            all_runs.extend(page)
            token = page.token
            if not token:
                break
        ranked = rank_candidates(all_runs, candidates, metrics, maximize, cohort)
        report['candidate_ranking'] = ranked
        missing = sorted(candidates - {r['name'] for r in ranked})
        require(not missing, f'Faltan candidatos comparables: {missing}', errors)
        selected = next((r for r in ranked if r['run_id'] == run_id), None)
        require(bool(selected), 'El champion no pertenece a los candidatos comparables de la búsqueda original.', errors)
        if selected and ranked:
            require(selected['metrics'] == ranked[0]['metrics'], 'Champion no tiene la mejor métrica de su cohorte original.', errors)
        # Recuperación REAL del alias, con firma y ejemplo.
        uri = f'models:/{name}@champion'
        model = mlflow.pyfunc.load_model(uri)
        signature = model.metadata.signature
        report['signature'] = str(signature) if signature else None
        require(signature is not None and signature.inputs is not None, 'Modelo sin firma de entrada.', errors)
        if not getattr(model.metadata, 'saved_input_example_info', None):
            warnings.append('No se encontró metadato del ejemplo guardado; revisar artefacto MLmodel.')
        if question == 'P1':
            from mibici.serving.contract import FEATURE_COLUMNS, SAMPLE_P1
            from mibici.serving.model_loader import MiBiciModelService
            if signature and signature.inputs:
                require([item.name for item in signature.inputs.inputs] == list(FEATURE_COLUMNS), 'Firma P1 distinta del contrato API.', errors)
            service = MiBiciModelService()
            result = service.predict(SAMPLE_P1)
            report['prediction_sample'] = result
            report['service_version'] = str(service.version)
            require(str(service.version) == str(version.version), 'El servicio carga una versión distinta del champion.', errors)
            import numpy as np
            values = np.asarray(result, dtype=float)
            require(values.size > 0 and bool(np.isfinite(values).all()) and bool((values >= 0).all()), 'Predicción P1 inválida.', errors)
        require(str(client.get_model_version_by_alias(name, 'champion').version) == str(version.version), 'El alias cambió durante la auditoría.', errors)
    except Exception as exc:
        errors.append(f'{type(exc).__name__}: {exc}')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--questions', nargs='+', choices=list(MODELS), default=list(MODELS))
    parser.add_argument('--output', type=Path, default=Path('docs/evidencias_final/registry_audit.json'))
    args = parser.parse_args()
    import mlflow
    from mlflow import MlflowClient
    tracking_uri = os.getenv('MLFLOW_TRACKING_URI', 'http://127.0.0.1:5000')
    registry_uri = os.getenv('MLFLOW_REGISTRY_URI', tracking_uri)
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_registry_uri(registry_uri)
    # Evitar una verificación P1 que esté apuntando a una versión fija o nombre diferente.
    if 'P1' in args.questions and (os.getenv('MIBICI_MODEL_VERSION') or os.getenv('MIBICI_MODEL_ALIAS', 'champion') != 'champion' or os.getenv('MIBICI_MODEL_NAME', MODELS['P1'][0]) != MODELS['P1'][0]):
        parser.error('Elimina overrides MIBICI_MODEL_VERSION/ALIAS/NAME antes de auditar P1.')
    client = MlflowClient(tracking_uri=tracking_uri, registry_uri=registry_uri)
    manifest = json.loads(Path('data/manifest/data_manifest.json').read_text(encoding='utf-8'))
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    tracked_dirty = bool(subprocess.check_output(['git','status','--porcelain','--untracked-files=no'], text=True).strip())
    report = {'generated_utc': datetime.now(timezone.utc).isoformat(), 'git_head': commit,
              'tracked_worktree_dirty': tracked_dirty, 'python': sys.version.split()[0], 'mlflow': mlflow.__version__,
              'local_manifest': {k:manifest.get(k) for k in ('data_version','complete','start_month','end_month','n_trips','n_stations')},
              'models': []}
    for question in dict.fromkeys(args.questions):
        report['models'].append(audit_model(client, mlflow, question, manifest.get('data_version')))
    report['status'] = 'PASS' if all(not row['errors'] for row in report['models']) and manifest.get('complete') is True else 'FAIL'
    report['scope'] = 'Solo modelos solicitados; no certifica despliegue, CI/CD ni reproducción completa.'
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str, allow_nan=False)+'\n', encoding='utf-8')
    for row in report['models']:
        print(f"{row['question']} | {row['name']} | v{row.get('version', '?')} | {'FAIL' if row['errors'] else 'PASS'}")
        for error in row['errors']:
            print('  ERROR:', error)
        for warning in row['warnings']:
            print('  AVISO:', warning)
    print(f"{report['status']} | {args.output}")
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
