"""
SQLite database files
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, create_engine
from sqlalchemy.ext.declarative import declarative_base

engine = create_engine('sqlite:///simulation.db')
Base = declarative_base()

__all__ = ['Humans', 'Vectors', 'Subregions']


class Humans(Base):
    """
    Table for Humans
    """

    __tablename__ = "humans"
    id = Column(Integer, primary_key=True)
    p_uuid = Column(String)
    subregion = Column(String)
    age = Column(Integer)
    sex = Column(String)
    Pregnant = Column(Boolean)
    Susceptible = Column(Boolean)
    Infected = Column(Boolean)
    Exposed = Column(Boolean)
    dayOfInf = Column(Integer)
    dayOfExp = Column(Integer)
    dayOfRec = Column(Integer)
    Resistant = Column(Boolean)


class Vectors(Base):
    """
    Table for Vectors
    """

    __tablename__ = "vectors"
    id = Column(Integer, primary_key=True)
    subregion = Column(String)
    range = Column(Float)
    lifetime = Column(Integer)
    Susceptible = Column(Boolean)
    Exposed = Column(Boolean)
    Infected = Column(Boolean)
    x = Column(String)
    y = Column(String)


Base.metadata.create_all(engine)
