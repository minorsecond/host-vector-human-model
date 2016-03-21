"""
SQLite database files
"""

from sqlalchemy import Column, Integer, String, Boolean, Float, create_engine
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
    uniqueID = Column(String)
    linkedTo = Column(String)  # Link uniqueID to another uniqueID in table for relationships (sexual transmission)
    subregion = Column(String)
    importer = Column(Boolean)
    importDay = Column(Integer)
    pregnant = Column(String)
    susceptible = Column(String, index=True)
    infected = Column(String, index=True)
    exposed = Column(String, index=True)
    recovered = Column(String, index=True)
    #dead = Column(String)
    dayOfInf = Column(Integer)
    dayOfExp = Column(Integer)
    x = Column(String)
    y = Column(String)


class Vectors(Base):
    """
    Table for Vectors
    """

    __tablename__ = "vectors"
    id = Column(Integer, primary_key=True, index=True)
    # uniqueID = Column(String)
    subregion = Column(String)
    modified = Column(Boolean)
    alive = Column(String)
    vector_range = Column(Float)
    birthday = Column(Integer)
    lifetime = Column(Integer)
    susceptible = Column(String, index=True)
    infected = Column(String, index=True)
    removed = Column(String)
    x = Column(String)
    y = Column(String)


class Log(Base):
    """
    Table for day-to-day list of infections, recovers, etc.
    """
    __tablename__ = "Log"
    id = Column(Integer, primary_key=True)
    Subregion = Column(String)
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


class vectorHumanLinks(Base):
    """
    Table to link vectors to humans within range
    """

    __tablename__ = 'vector_human_links'
    id = Column(Integer, primary_key=True)
    human_id = Column(Integer, index=True)
    vector_id = Column(Integer, index=True)
    distance = Column(Float)

Base.metadata.create_all(engine)
