"""
SQLite database files
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, create_engine
from sqlalchemy.ext.declarative import declarative_base

engine = create_engine('sqlite:///simulation.db')
Base = declarative_base()

__all__ = ['Humans', 'Vectors']


class Humans(Base):
    """
    Table for Humans
    """

    __tablename__ = "Humans"
    id = Column(Integer, primary_key=True)
    p_uuid = Column(String)
    subregion = Column(String)
    age = Column(Integer)
    sex = Column(String)
    pregnant = Column(String)
    susceptible = Column(String)
    infected = Column(String)
    exposed = Column(String)
    recovered = Column(String)
    dayOfInf = Column(Integer)
    dayOfExp = Column(Integer)
    dayOfRec = Column(Integer)
    resistant = Column(String)


class Vectors(Base):
    """
    Table for Vectors
    """

    __tablename__ = "vectors"
    id = Column(Integer, primary_key=True)
    subregion = Column(String)
    range = Column(Float)
    lifetime = Column(Integer)
    susceptible = Column(Boolean)
    exposed = Column(Boolean)
    infected = Column(Boolean)
    x = Column(String)
    y = Column(String)


Base.metadata.create_all(engine)
