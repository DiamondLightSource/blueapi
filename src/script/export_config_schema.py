import json

from blueapi.config import ApplicationConfig


def print_application_config_json_schema():
    # print(json.dumps(ApplicationConfig.model_json_schema()))
    with open("helm/blueapi/config_schema.json", "w") as file:
        file.write(json.dumps(ApplicationConfig.model_json_schema()))


if __name__ == "__main__":
    print_application_config_json_schema()
