from __future__ import absolute_import

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from frontera.contrib.backends import CommonBackend
from frontera.contrib.backends.sqlalchemy.components import Metadata, Queue, States
from frontera.contrib.backends.sqlalchemy.models import DeclarativeBase
from frontera.utils.misc import load_object


class SQLAlchemyBackend(CommonBackend):
    def __init__(self, manager):
        self.manager = manager
        settings = manager.settings
        engine = settings.get('SQLALCHEMYBACKEND_ENGINE')
        engine_echo = settings.get('SQLALCHEMYBACKEND_ENGINE_ECHO')
        drop_all_tables = settings.get('SQLALCHEMYBACKEND_DROP_ALL_TABLES')
        clear_content = settings.get('SQLALCHEMYBACKEND_CLEAR_CONTENT')
        models = settings.get('SQLALCHEMYBACKEND_MODELS')

        self.engine = create_engine(engine, echo=engine_echo)
        self.models = dict([(name, load_object(klass)) for name, klass in models.items()])

        if drop_all_tables:
            DeclarativeBase.metadata.drop_all(self.engine)
        DeclarativeBase.metadata.create_all(self.engine)

        self.session_cls = sessionmaker()
        self.session_cls.configure(bind=self.engine)

        if clear_content:
            session = self.session_cls()
            for name, table in DeclarativeBase.metadata.tables.items():
                session.execute(table.delete())
            session.close()
        self._metadata = Metadata(self.session_cls, self.models['MetadataModel'],
                                  settings.get('SQLALCHEMYBACKEND_CACHE_SIZE'))
        self._states = States(self.session_cls, self.models['StateModel'],
                              settings.get('STATE_CACHE_SIZE_LIMIT'))
        self._queue = self._create_queue(settings)

    def frontier_stop(self):
        super(SQLAlchemyBackend, self).frontier_stop()
        self.engine.dispose()

    def _create_queue(self, settings):
        return Queue(self.session_cls, self.models['QueueModel'], 1)

    @property
    def queue(self):
        return self._queue

    @property
    def metadata(self):
        return self._metadata

    @property
    def states(self):
        return self._states


class FIFOBackend(SQLAlchemyBackend):
    component_name = 'SQLAlchemy FIFO Backend'

    def _create_queue(self, settings):
        return Queue(self.session_cls, self.models['QueueModel'], 1, ordering='created')


class LIFOBackend(SQLAlchemyBackend):
    component_name = 'SQLAlchemy LIFO Backend'

    def _create_queue(self, settings):
        return Queue(self.session_cls, self.models['QueueModel'], 1, ordering='created_desc')


class DFSBackend(SQLAlchemyBackend):
    component_name = 'SQLAlchemy DFS Backend'

    def _create_queue(self, settings):
        return Queue(self.session_cls, self.models['QueueModel'], 1)

    def _get_score(self, obj):
        return -obj.meta['depth']


class BFSBackend(SQLAlchemyBackend):
    component_name = 'SQLAlchemy BFS Backend'

    def _create_queue(self, settings):
        return Queue(self.session_cls, self.models['QueueModel'], 1)

    def _get_score(self, obj):
        return obj.meta['depth']


BASE = CommonBackend
LIFO = LIFOBackend
FIFO = FIFOBackend
DFS = DFSBackend
BFS = BFSBackend