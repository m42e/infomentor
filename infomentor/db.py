from infomentor import model
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

_session = None


def get_db(filename="infomentor.db"):
    """Get the database session for infomentor"""
    global _session
    if _session is None:
        engine = create_engine(f"sqlite:///{filename}")
        model.ModelBase.metadata.create_all(engine)
        model.ModelBase.metadata.bind = engine
        DBSession = sessionmaker(bind=engine)
        _session = DBSession()
    return _session
