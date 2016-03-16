"""
SQLite database files
"""

from sqlalchemy import Column, Integer, String, Float, create_engine
from sqlalchemy.ext.declarative import declarative_base

engine = create_engine('sqlite:///simulation.epi')
Base = declarative_base()

__all__ = ['Humans', 'Vectors']


class Humans(Base):
    """
    Table for Humans
    """

    __tablename__ = "Humans"
    id = Column(Integer, primary_key=True)
    uniqueID = Column(String)
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
    x = Column(String)
    y = Column(String)


class Vectors(Base):
    """
    Table for Vectors
    """

    __tablename__ = "vectors"
    id = Column(Integer, primary_key=True)
    uniqueID = Column(String)
    subregion = Column(String)
    range = Column(Float)
    lifetime = Column(Integer)
    susceptible = Column(String)
    exposed = Column(String)
    infected = Column(String)
    x = Column(String)
    y = Column(String)


class Log(Base):
    """
    Table for day-to-day list of infections, recovers, etc.
    """
    __tablename__ = "Log"
    id = Column(Integer, primary_key=True)
    Day = Column(Integer)
    nSusceptible = Column(Integer)
    nExposed = Column(Integer)
    nInfected = Column(Integer)
    nRecovered = Column(Integer)
    nDeaths = Column(Integer)
    nBirthInfections = Column(Integer)

Base.metadata.create_all(engine)
