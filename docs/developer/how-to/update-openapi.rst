Update the openapi schema
-------------------------

If you change any of the code in src/blueapi/service/main, it is imperative that
you update the openapi schema to reflect these changes. There is a test to check
that this has been done.

Simply type,
```
blueapi schema -u
```

To update. You can also specify a `-o` tag to generate the schema elsewhere - note
this doesn't work in combination to the `-u` tag.
