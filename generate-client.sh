
podman run --rm \
  -v ${PWD}:/local openapitools/openapi-generator-cli generate \
  -i /local/docs/reference/schema-for-autogen.yaml \
  -g python-pydantic-v1 \
  -o /local/tmp

NEW_PATH=src/blueapi
rm -rf "$NEW_PATH"/openapi_client
mv -f tmp/openapi_client $NEW_PATH

echo "__all__ = [ApiClient]" > "$NEW_PATH"/openapi_client/__init__.py
rm -rf tmp
