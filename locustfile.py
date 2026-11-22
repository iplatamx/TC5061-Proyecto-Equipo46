"""Escenario Locust para POST /predict con entradas válidas del contrato P1."""

import random

from locust import HttpUser, between, task


class MiBiciPredictionUser(HttpUser):
    wait_time = between(0.2, 0.8)

    @task
    def predict(self):
        day = random.randint(0, 6)
        payload = {
            "station_id": random.randint(1, 484),
            "departures_this_hour": random.randint(0, 40),
            "arrivals_this_hour": random.randint(0, 40),
            "departures_mean_last_24h": round(random.uniform(0, 30), 2),
            "departures_mean_last_168h": round(random.uniform(0, 30), 2),
            "target_hour": random.randint(0, 23),
            "target_dayofweek": day,
            "target_is_weekend": int(day >= 5),
        }
        self.client.post("/predict", json=payload, name="/predict")
