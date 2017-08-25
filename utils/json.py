import asyncio
import json
import uuid
import os


def convert_to_int_keys(d):
    for key in d.copy().keys():
        d[int(key)] = d.pop(key)


class JsonIO:
    def __init__(self, filename, folder='', *, loop=None, autoload=True, sync_load=False, after_load=lambda: None):
        self._loop = loop or asyncio.get_event_loop()
        self._lock = asyncio.Lock(loop=self._loop)
        self._after_load = after_load
        self.data_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', folder)
        self.filename = filename
        self.file = os.path.join(self.data_path, self.filename) + '.json'
        if autoload and sync_load:
            self._from_file()
        elif autoload:
            self._loop.create_task(self.load())

    def _to_file(self):
        temp = os.path.join(self.data_path, f'{uuid.uuid4()}-{self.filename}.tmp')
        with open(temp, 'w', encoding='utf-8') as fp:
            json.dump(self, fp, indent=4, ensure_ascii=True)
        os.replace(temp, self.file)

    def _from_file(self):
        try:
            with open(self.file, 'r', encoding='utf-8') as fp:
                self.update(json.load(fp))
            self._after_load()
        except FileNotFoundError:
            pass

    async def save(self):
        with await self._lock:
            await self._loop.run_in_executor(None, self._to_file)

    async def load(self):
        self.clear()
        with await self._lock:
            await self._loop.run_in_executor(None, self._from_file)


class Dict(JsonIO, dict):
    def __init__(self, *args, int_keys=False, **kwargs):
        after_load = kwargs.pop('after_load', lambda: None)
        if int_keys:
            def after():
                convert_to_int_keys(self)
                after_load()
        else:
            after = after_load
        super().__init__(*args, after_load=after, **kwargs)


class List(JsonIO, list):
    def update(self, *args):
        self.extend(*args)
