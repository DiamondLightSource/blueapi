import json

from blueapi.config import ApplicationConfig


def print_application_config_json_schema():
    print(json.dumps(ApplicationConfig.model_json_schema()))


if __name__ == "__main__":
    print_application_config_json_schema()
