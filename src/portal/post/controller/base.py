import season
import datetime

class Controller(wiz.controller("base")):
    def __init__(self):
        super().__init__()

    def json_default(self, value):
        if isinstance(value, datetime.date):
            return value.strftime('%Y-%m-%d %H:%M:%S')
        return str(value).replace('<', '&lt;').replace('>', '&gt;')
