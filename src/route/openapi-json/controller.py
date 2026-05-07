fs = wiz.project.fs()
document = fs.read("docs/api/openapi.json", "{}")
wiz.response.send(document, content_type="application/json; charset=utf-8")
