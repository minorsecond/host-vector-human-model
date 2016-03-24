"""
SQLite database files
"""
from geoalchemy2 import Geometry
from sqlalchemy import Column, Integer, String, Boolean, Float, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base

# engine = create_engine('sqlite:///simulation.epi')
engine = create_engine('postgresql://simulator:Rward0232@localhost/simulation')
Base = declarative_base()

__all__ = ['Humans', 'Vectors', 'Log', 'vectorHumanLinks']


class Humans(Base):
    """
    Table for Humans
    """

    __tablename__ = "Humans"
    id = Column(Integer, primary_key=True, index=True)
    uniqueID = Column(String, index=True)
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
    geom = Column(Geometry('POINT', srid=2845))


class Vectors(Base):
    """
    Table for Vectors
    """

    __tablename__ = "vectors"
    id = Column(Integer, primary_key=True, index=True)
    uniqueID = Column(String, index=True)
    subregion = Column(String)
    modified = Column(Boolean)
    alive = Column(String)
    vector_range = Column(Float)
    birthday = Column(Integer)
    lifetime = Column(Integer)
    susceptible = Column(String, index=True)
    infected = Column(String, index=True)
    removed = Column(String)
    geom = Column(Geometry('POINT', srid=2845))


class Log(Base):
    """
    Table for day-to-day list of infections, recovers, etc.
    """
    __tablename__ = "Log"
    id = Column(Integer, primary_key=True)
    subregion = Column(String)
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
    human_id = Column(Integer, ForeignKey(Humans.id), index=True)
    vector_id = Column(Integer, ForeignKey(Vectors.id), index=True)
    distance = Column(Float)


class subRegion(Base):
    """
    Table containing subregion polys
    """

    __tablename__ = 'subregions'
    id = Column(Integer, primary_key=True)
    subregion_id = Column(String, index=True)
    population = Column(Integer)
    area = Column(Float)
    geom = Column(Geometry('POLYGON', srid=2845))


Humans.__table__.create(engine, checkfirst=True)
Vectors.__table__.create(engine, checkfirst=True)
subRegion.__table__.create(engine, checkfirst=True)

Base.metadata.create_all(engine, checkfirst=True)
