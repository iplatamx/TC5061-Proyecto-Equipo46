"""Pruebas de la selección de candidatos; no simulan evidencia de un Registry real."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace as NS

spec = importlib.util.spec_from_file_location('final_registry_audit', Path(__file__).resolve().parents[1] / 'scripts/audit_final_registry.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def run(name, run_id, value, version='hash-a', status='FINISHED', uri='models:/m-123'):
    return NS(info=NS(run_id=run_id, status=status), data=NS(tags={'mlflow.runName':name,'data_version':version,'logged_model_uri':uri}, params={}, metrics={'validation_mae':value}))


def test_min_mae_only_same_cohort():
    runs = [run('P1-HGB-01','a',0.8),run('P1-HGB-02','b',0.7),run('P1-HGB-03','c',0.1,'hash-b')]
    _, names, metrics, maximize = audit.MODELS['P1']
    assert [row['run_id'] for row in audit.rank_candidates(runs,names,metrics,maximize,'hash-a')] == ['b','a']


def test_invalid_candidates_are_excluded():
    runs = [run('P1-HGB-01','a',float('nan')),run('P1-HGB-02','b',0.2,status='FAILED'),run('P1-HGB-03','c',0.1,uri=''),run('other','d',0.1)]
    _, names, metrics, maximize = audit.MODELS['P1']
    assert audit.rank_candidates(runs,names,metrics,maximize,'hash-a') == []


def test_maximize_uses_secondary_metric():
    a,b = run('P2-HGB-01','a',0),run('P2-HGB-02','b',0)
    a.data.metrics = dict(validation_f1=0.5, validation_recall=0.7, validation_balanced_accuracy=0.6)
    b.data.metrics = dict(validation_f1=0.5, validation_recall=0.8, validation_balanced_accuracy=0.5)
    _, names, metrics, maximize = audit.MODELS['P2']
    assert [row['run_id'] for row in audit.rank_candidates([a,b],names,metrics,maximize,'hash-a')] == ['b','a']
