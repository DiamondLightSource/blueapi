
echo "Starting the refresh of the REST client library."
podman run --rm \
  -v ${PWD}:/local openapitools/openapi-generator-cli generate \
  -i /local/docs/reference/schema-for-autogen.yaml \
  -g python-pydantic-v1 \
  -o /local/tmp

NEW_PATH=src/blueapi
rm -rf "$NEW_PATH"/openapi_client
mv -f tmp/openapi_client $NEW_PATH

# sed -i 's/from openapi_client/from project.openapi_client/g' src/project/openapi_client/__init__.py
find src/blueapi/openapi_client -type f -name '*.py' -exec sed -i 's/from openapi_client/from blueapi.openapi_client/g' {} +
echo "__all__ = [ApiClient]" >> "$NEW_PATH"/openapi_client/__init__.py
rm -rf tmp
echo "API client integration complete."