"""
SQLite database files
"""

from geoalchemy import *
from sqlalchemy import Integer, String, Boolean, Float, create_engine
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
    geom = GeometryColumn(Point(2))


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
    geom = GeometryColumn(Point(2))


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
    human_id = Column(Integer, index=True, ForeignKey=(Humans.id))
    vector_id = Column(Integer, index=True, ForeignKey=(Vectors.id))
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
    geom = GeometryColumn(Polygon(2))


GeometryDDL(Vectors.__table__)
GeometryDDL(Humans.__table__)
GeometryDDL(subRegion.__table__)

Base.metadata.create_all(engine)
