"""
Robert Ross Wardrup
Create points and make sure they're within the subregion polygons.
"""

import shapefile

def reader(name, fid):
    """
    Takes shapefile name, reads shapefile, and returns it
    takes name - the string name of the shapefile, and fid - the name of the feature for which to grab verticies
    """

    features = shapefile.Reader(name)
    shapes = features.shapeRecords()  # We want the points from this, from a certain feature ID

    #TODO: Make a list of all block groups in shapefile, and iterate through each one, building a dict of points for each group

    points = shapes[3].shape.points[0:2]  # Will need to change this depending on my shape data.

