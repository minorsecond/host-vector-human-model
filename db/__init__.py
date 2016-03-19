"""
SQLite database files
"""

from sqlalchemy import Column, Integer, String, Boolean, create_engine
from sqlalchemy.ext.declarative import declarative_base

engine = create_engine('sqlite:///simulation.epi')
Base = declarative_base()

__all__ = ['Humans', 'Vectors']


class Humans(Base):
    """
    Table for Humans
    """

    __tablename__ = "Humans"
    id = Column(Integer, primary_key=True, index=True)
    # uniqueID = Column(String)
    subregion = Column(String)
    importer = Column(Boolean)
    importDay = Column(Integer)
    # age = Column(Integer)
    # sex = Column(String)
    pregnant = Column(String)
    # initial_susceptible = Column(Boolean)
    susceptible = Column(String, index=True)
    infected = Column(String, index=True)
    exposed = Column(String, index=True)
    recovered = Column(String, index=True)
    #dead = Column(String)
    dayOfInf = Column(Integer)
    dayOfExp = Column(Integer)
    # dayOfRec = Column(Integer)
    # resistant = Column(String)
    # x = Column(String)
    #y = Column(String)


class Vectors(Base):
    """
    Table for Vectors
    """

    __tablename__ = "vectors"
    id = Column(Integer, primary_key=True, index=True)
    # uniqueID = Column(String)
    subregion = Column(String)
    alive = Column(String)
    birthday = Column(Integer)
    lifetime = Column(Integer)
    susceptible = Column(String, index=True)
    infected = Column(String, index=True)
    removed = Column(String)
    # x = Column(String)
    #y = Column(String)


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
    nInfectedVectors = Column(Integer)
    nSuscVectors = Column(Integer)
    nRemovedVectors = Column(Integer)

Base.metadata.create_all(engine)
