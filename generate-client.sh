
if [ "$INSIDE_DEVCONTAINER" == "true" ]; then
    echo "This script is not allowed to run inside the devcontainer as it needs podman"
    exit 1
fi

echo "Starting the refresh of the REST client library."

podman run --rm \
  -v ${PWD}:/local openapitools/openapi-generator-cli generate \
  -i /local/docs/reference/schema-for-autogen.yaml \
  -g python-pydantic-v1 \
  -o /local/tmp

NEW_PATH=src/blueapi
rm -rf "$NEW_PATH"/openapi_client
mv -f tmp/openapi_client $NEW_PATH

# Update 'from ... import ...' imports in all Python files
find src/blueapi/openapi_client -type f -name '*.py' -exec sed -i 's/from openapi_client/from blueapi.openapi_client/g' {} +

# Update 'import ...' imports in all Python files
find src/blueapi/openapi_client -type f -name '*.py' -exec sed -i 's/import openapi_client/import blueapi.openapi_client/g' {} +

echo "__all__ = [ApiClient]" >> "$NEW_PATH"/openapi_client/__init__.py
rm -rf tmp
echo "API client integration complete."
