import season
import datetime
import json
import os
from flask import request

class Controller:
    def __init__(self):
        wiz.session = wiz.model("portal/season/session").use()
        sessiondata = wiz.session.get()
        wiz.response.data.set(session=sessiondata)

        def query(key=None, default=None):
            method = wiz.request.method().upper()
            if method == "GET":
                body = request.args.to_dict()
            else:
                if request.is_json:
                    body = request.get_json(silent=True)
                    if body is None or isinstance(body, dict) is False:
                        body = {}
                else:
                    body = request.form.to_dict()

            if key is None:
                return body
            if key not in body:
                if isinstance(default, bool) and default is True:
                    wiz.response.abort(400)
                return default
            return body[key]
        wiz.request.query = query

        lang = wiz.request.query("lang", None)
        if lang is not None:
            wiz.response.lang(lang)
            wiz.response.redirect(wiz.request.uri())

    def json_default(self, value):
        if isinstance(value, datetime.date):
            return value.strftime('%Y-%m-%d %H:%M:%S')
        return str(value).replace('<', '&lt;').replace('>', '&gt;')
