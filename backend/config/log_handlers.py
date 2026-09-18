"""Async buffered Elasticsearch logging handler."""
import datetime
import logging
import os
import queue
import threading


class ElasticsearchLogHandler(logging.Handler):
    """
    Buffered async handler — sends log records to Elasticsearch via bulk API.
    Reads all config from environment variables (ELK_*, LOG_*, SERVICE_NAME, ENVIRONMENT).
    """

    def __init__(self):
        super().__init__()
        self._enabled = os.getenv('ELK_ENABLED', 'true').lower() in ('true', '1', 'yes')
        if not self._enabled:
            return
        self._host = os.getenv('ELK_HOST', 'http://82.223.29.91:9200')
        self._index_prefix = os.getenv('ELK_INDEX_PREFIX', 'app-logs')
        self._auth_type = os.getenv('ELK_AUTH_TYPE', 'basic').lower()
        self._username = os.getenv('ELK_USERNAME', '')
        self._password = os.getenv('ELK_PASSWORD', '')
        self._api_key = os.getenv('ELK_API_KEY', '')
        self._buffer_size = int(os.getenv('ELK_BUFFER_SIZE', '100'))
        self._flush_interval = int(os.getenv('ELK_FLUSH_INTERVAL', '5'))
        self._service_name = os.getenv('SERVICE_NAME', 'app')
        self._environment = os.getenv('ENVIRONMENT', 'dev')
        self._queue: queue.Queue = queue.Queue()
        self._client = None
        self._lock = threading.Lock()
        self._flush_thread = threading.Thread(target=self._flush_loop, daemon=True)
        self._flush_thread.start()

    def _get_client(self):
        if self._client is not None:
            return self._client
        with self._lock:
            if self._client is not None:
                return self._client
            try:
                from elasticsearch import Elasticsearch
                kwargs: dict = {'hosts': [self._host]}
                if self._auth_type == 'basic' and self._username:
                    kwargs['basic_auth'] = (self._username, self._password)
                elif self._auth_type == 'api_key' and self._api_key:
                    kwargs['api_key'] = self._api_key
                self._client = Elasticsearch(**kwargs)
            except Exception:
                pass
        return self._client

    def _flush_loop(self) -> None:
        import time
        buf: list = []
        while True:
            time.sleep(self._flush_interval)
            while not self._queue.empty():
                try:
                    buf.append(self._queue.get_nowait())
                except queue.Empty:
                    break
            if buf:
                self._bulk_send(buf)
                buf.clear()

    def _bulk_send(self, docs: list) -> None:
        client = self._get_client()
        if client is None:
            return
        try:
            date_suffix = datetime.date.today().strftime("%Y.%m.%d")
            index = f"{self._index_prefix}-{date_suffix}"
            operations = []
            for doc in docs:
                operations.append({'index': {'_index': index}})
                operations.append(doc)
            client.bulk(operations=operations)
        except Exception:
            pass

    def emit(self, record: logging.LogRecord) -> None:
        if not self._enabled:
            return
        try:
            doc = {
                '@timestamp': datetime.datetime.utcnow().isoformat() + 'Z',
                'level': record.levelname,
                'logger': record.name,
                'module': record.module,
                'message': self.format(record),
                'service': {'name': self._service_name},
                'environment': self._environment,
            }
            if record.exc_info:
                doc['exception'] = self.formatException(record.exc_info)
            self._queue.put_nowait(doc)
            if self._queue.qsize() >= self._buffer_size:
                buf = []
                while not self._queue.empty():
                    try:
                        buf.append(self._queue.get_nowait())
                    except queue.Empty:
                        break
                if buf:
                    threading.Thread(target=self._bulk_send, args=(buf,), daemon=True).start()
        except Exception:
            self.handleError(record)
