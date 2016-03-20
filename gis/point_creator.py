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
    fields = features.fields[1:]
    field_names = [field[0] for field in fields]

    for sr in features.shapeRecords():
        yield dict(zip(field_names, sr.record))


def grab_vertices(filename):
    """
    Gets vertices of polygons for creating points
    :param list: A list of subregion IDs for which to obtain verticies
    :return list of dictionaries containing an entry for each subregion
    """
    sf = shapefile.Reader(filename)
    shapeRecs = sf.shapeRecords()
    points = []
    list_of_subregions = []


    for i in range(len(list)):
        id = shapeRecs[i].record[1:2]
        points.append(shapeRecs[i].shape.points[:])  # Make a list of all points for the polygon
        population = shapeRecs[i].record[2:3]
        area = shapeRecs[i].record[3:4]
        subregion = {
            'id':           id,
            'vertices':     points,
            'area':         area,
            'population':   population
        }

        list_of_subregions.append(subregion)

        return list_of_subregions

if __name__ == '__main__':
    shapefile_reader()
