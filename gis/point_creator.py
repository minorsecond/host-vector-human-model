"""
Robert Ross Wardrup
Create points and make sure they're within the subregion polygons.
"""

import shapefile

name = "/home/rwardrup/DEV/host-vector-human-model/tarrant_tracts/cartodb_st_clusters"

def shapefile_reader(name):
    """
    Takes shapefile name, reads shapefile, and returns it
    takes name - the string name of the shapefile, and fid - the name of the feature for which to grab verticies
    """

    features = shapefile.Reader(name)
    fields = features.fields[0:]
    field_names = [field[0] for field in fields]

    for sr in features.shapeRecords():
        yield dict(zip(field_names, sr.record))

if __name__ == '__main__':
    shapefile_reader()
