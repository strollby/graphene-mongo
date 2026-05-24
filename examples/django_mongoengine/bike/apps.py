from django.apps import AppConfig


class BikeConfig(AppConfig):
    name = "bike"

    def ready(self):
        from telemetry import setup_telemetry
        setup_telemetry()
