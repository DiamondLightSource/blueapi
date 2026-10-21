from bluesky.callbacks.tiled_writer import TiledWriter

from blueapi.config import ApplicationConfig, ServiceAccount, TiledConfig
from blueapi.utils.invalid_config_error import InvalidConfigError


class TiledManager:
    config: TiledConfig | None

    def __init__(self, config: ApplicationConfig) -> None:

        if (tiled_conf := config.tiled) is not None and tiled_conf.enabled:
            if config.env.metadata is None:
                raise InvalidConfigError(
                    "Tiled has been configured but `instrument` metadata is not set - "
                    "this field is required to make authorization decisions."
                )
            if isinstance(tiled_conf.authentication, ServiceAccount):
                if config.oidc is None:
                    raise InvalidConfigError(
                        "Tiled has been configured but oidc configuration is missing "
                        "this field is required to make authorization decisions."
                    )
                tiled_conf.authentication.token_url = config.oidc.token_endpoint

        self.config = tiled_conf or None


# submit_task

# if context().tiled_conf is not None:
#     md = config().env.metadata
#     # We raise an InvalidConfigError on setting tiled_conf if this isn't set
#     assert md
#     metadata["tiled_access_tags"] = [
#         access_blob(task_request.instrument_session, md.instrument)
#     ]
