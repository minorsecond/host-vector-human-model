"""
2016 - Robert Ross Wardrup
A SEIR simulation that uses SQLite and CSV Census files to define population paramaters
Please run this on a rotating hard drive - building large
"""

# TODO: Switch all random calls to use numpy
# TODO: Output to shapefile
# TODO: Read and write config file

import configparser
import csv
import logging
import os.path
import random
from sys import exit as die
from time import sleep
from uuid import uuid4 as uuid

import numpy as np
from igraph import *
from sqlalchemy import create_engine, MetaData, Table
from sqlalchemy.orm import sessionmaker

from db import Humans, Vectors, Log, vectorHumanLinks
from gis import point_creator

global working_directory_set

working_directory_set = False

# Simulation parameters
days_to_run = 365
random.seed(5)

# Epidemic parameters
causes_death = False
death_chance = .001
beta = 0.2
gamma = .5  # TODO: See how this interacts with infectious period.
sigma = .35  # TODO: See how this interacts with infectious period.
mu = .1
theta = .1  # mother -> child transmission
birthrate = 0  # birth rate
kappa = .1  # sexual contact
zeta = .1  # blood transfusion
tau = .75  # chance a mosquito picks up zika from human
infectious_period = 7
latent_period = 7

# Human population parameters
initial_susceptible = 750000  # Unused with subregions file
initial_exposed = 0
initial_infected = 1
contact_rate = 1
number_of_importers = 50  # number of people to bring back disease from foreign lands, over the study period
bite_limit = 5  # Number of bites per human, per day.

# Vector population parameters
gm_flag = False
mosquito_susceptible_coef = 500  # mosquitos per square kilometer
mosquito_exposed = 0
mosquito_init_infectd = 100
biting_rate = 5  # average bites per day
mosquito_season_start = 78  # Day of year to begin mosquito presence
mosquito_season_end = 266  # Day of year to end mosquito presence

# Set up logging
logger = logging.getLogger("epiSim")
logger.setLevel(logging.INFO)
fh = logging.FileHandler("epiSim.log")
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
logger.addHandler(fh)


def clear_screen():
    """
    Clears the screen to keep output tidy
    :return:
    """

    os.system('cls' if os.name == 'nt' else 'clear')


def create_graph():
    """
    Creates graph for plotting output
    """

    # TODO: Needs to use UID from each table to avoid ID collision
    id_list = []
    host_id_list = []
    _hosts = []
    _vectors = []
    tmp_links = []
    _links = {}
    links = []
    vector_id_list = []
    edge_list = []

    hosts = session.query(Humans).yield_per(1000)
    for host in hosts:
        host_id_list.append(host.id)

    for i in range(25):
        _hosts.append(random.choice(host_id_list))  # Choose n random hosts

    for host in _hosts:  # Get list of vectors for each host
        print(host)
        _links = session.query(vectorHumanLinks).filter_by(human_id=host)

        for l in _links:
            print('link: {0} to {1}'.format(l.human_id, l.vector_id))
            tmp_links.append(l.vector_id)  # Add vectors to a list

        # Append a list of vectors linked to a host to a dictionary
        _links = {
            'host_id':  host,
            'vector_ids':   tmp_links
        }

        links.append(_links)  # Append _links dict to a list of dicts

    print(links)

    # Copy lists
    host_id_list = _hosts
    vector_id_list = tmp_links

    n = len(host_id_list) + len(vector_id_list)

    id_list = host_id_list + vector_id_list

    g = Graph()
    g.add_vertices(n)
    g.vs["uid"] = id_list

    for i in g.vs:
        if i['uid'] in vector_id_list:
            i["group"] = "vector"
            vector_id = i['uid']
            vector = session.query(vectorHumanLinks).filter_by(vector_id=i['uid'])
            for v in vector:
                counter = 0
                human_id = v.human_id
                connection = (vector_id, human_id)

                for x in g.vs:
                    if x['uid'] in host_id_list:
                        x["group"] = "host"

                        if x['uid'] == human_id:
                            edge_list.insert(counter, connection)
                counter += 1

    input('Edges: '.format(edge_list))

    g.add_edges(edge_list)

    layout = g.layout("lgl")
    plot(g, layout=layout)


def prompt(question):
    """
    Simple user y/n prompt
    :param question:
    :return:
    """

    reply = str(input(question + ' (y/n): ')).lower().strip()
    if reply[0] == 'y':
        return True
    if reply[0] == 'n':
        return False
    else:
        return question("Try again: ")


def point_in_poly(x, y, poly):
    """
    Ray casting method of determining if point lies within a polygon.
    """

    n = len(poly)
    inside = False

    p1x, p1y = poly[0]
    for i in range(n + 1):
        p2x, p2y = poly[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xints = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xints:
                        inside = not inside
        p1x, p1y = p2x, p2y

    return inside


def create_bboxes(list_coordinates):
    """
    Creates bounding boxes based on SW and NE coordinates
    """

    # Create bounding boxes to estimate location before pinpointing, to speed it up.
    sw_x = float(list_coordinates[0])
    sw_y = float(list_coordinates[1])
    sw = (sw_x, sw_y)

    ne_x = float(list_coordinates[2])
    ne_y = float(list_coordinates[3])
    ne = (ne_x, ne_y)

    nw_x = sw_x
    nw_y = ne_y
    nw = (nw_x, nw_y)

    se_x = ne_x
    se_y = sw_y
    se = (se_x, se_y)

    bounding_box = [sw, nw, ne, se]

    return bounding_box


def random_points(subregion_dictionary):
    """
    Random points within bounding box
    """

    bbox = create_bboxes(subregion_dictionary['bbox'])
    poly = subregion_dictionary['vertices']

    x_values = [x[0] for x in bbox]
    x_min = min(x_values)
    x_max = max(x_values)

    y_values = [x[1] for x in bbox]
    y_min = min(y_values)
    y_max = max(y_values)

    x = random.uniform(x_min, x_max)
    y = random.uniform(y_min, y_max)

    while not point_in_poly(x, y, poly):  # Make sure point does not fall outside subregion
        x = random.uniform(x_min, x_max)
        y = random.uniform(y_min, y_max)

    coordinates = [x, y]

    return coordinates


def build_population():
    """
    Builds population with parameters
    :return: Dict of dicts N size, with parameters
    """

    subregions_list = []

    #in_subregion_data = os.path.join(working_directory, 'subregions.csv')
    in_subregion_data = os.path.join(working_directory)
    sub_regions_dict = shape_subregions(in_subregion_data)
    count = 1

    for i in sub_regions_dict:

        subregion = i['id']  # subregion ID
        pop = int(i['population'])  # grab population from subregion dict
        ID_list = []

        clear_screen()
        print("Building {0} hosts for subregion {1} of {2}".format(pop, count, len(sub_regions_dict)))

        population = dict(
            (x, {
                'uuid': str(uuid()),
                'linkedTo': None,
                'subregion': subregion,
                'importer': False,  # Brings disease in from another place
                'importDay': None,
                'age': random.randint(0, 99),
                'sex': random.choice(['Male', 'Female']),
                'pregnant': 'False',
                'susceptible': 'True',
                'infected': 'False',
                'exposed': 'False',
                'recovered': 'False',
                'dayOfInf': 0,
                'dayOfExp': 0,
                'recState': 0,
                'x': random_points(i)[0],
                'y': random_points(i)[1]
            }) for x in range(pop)
        )

        for x in population:  # assign pregnancy to some of population  This is duplicated.  TODO: figure out which one works
            if population[x].get('age') >= 18:
                ID_list.append(population[x].get('uuid'))
            if population[x].get('sex') == "Female":
                if population[x].get('age') >= 15 and population[x].get('age') < 51:
                    if random.uniform(0, 1) < .4:
                        population[x]['pregnant'] = 'True'

        for y in population:  # This must be a separate loop so that the ID_list is full before it runs.
            if not population[y].get('linkedTo'):
                if population[y].get('age') >= 18:
                    link_id = None
                    if random.uniform(0, 1) < .52:
                        link_id = random.choice(ID_list)
                        while link_id == population[y].get('uuid'):
                            link_id = random.choice(ID_list)
                        ID_list.remove(link_id)

                        population[y]['linkedTo'] = link_id
                        for z in population:
                            if population.get('uuid') == population[y].get('linkedTo'):
                                population[z]['linkedTo'] = population[y]['uuid']


        subregions_list.append(population)
        count += 1

    return subregions_list


def vector_lifetime(gm):
    """
    Calculates vector lifetime based on if vector is genetically modified or not
    """

    if gm:
        lifetime = random.choice([random.gauss(15, 2)], 0)  # TODO: Find a better method - this will yield ~50% RIDL
    else:
        lifetime = random.gauss(15, 2)

    return lifetime


def build_vectors():
    """
    Builds vector population
    :return: Dict of dicts N size, with parameters
    """

    global gm_flag

    subregions_list = []
    count = 0
    infected_vectors = 0
    mosquito_season = list(range(mosquito_season_start, mosquito_season_end))

    in_subregion_data = os.path.join(working_directory)
    sub_regions_dict = sub_regions_dict = shape_subregions(in_subregion_data)

    # Flag for adding modified mosquitos to population.
    if gm_flag:
        modified = True
    else:
        modified = False

    for i in sub_regions_dict:
        subregion = i['id']  # subregion ID
        area = float(i['area'])  # get area from dict
        vector_pop = int((area / 1000000) * mosquito_susceptible_coef)  # sq. meters to square km

        clear_screen()
        print("Building {0} vectors for subregion {1} of {2}".format(vector_pop, count, len(sub_regions_dict)))

        vector_population = dict(
            (x, {
                'uuid': str(uuid()),
                'subregion': subregion,
                'modified': modified,
                'range': random.gauss(90, 2),  # 90 meters or so
                'alive': 'False',  # They come to life on their birthdays
                'birthday': random.choice(mosquito_season),
                'lifetime': vector_lifetime(gm_flag),  # in days
                'susceptible': 'False',
                'exposed': 'False',
                'infected': 'False',
                'removed': 'False',
                'x': random_points(i)[0],
                'y': random_points(i)[1]
            }) for x in range(vector_pop)
        )

        # Infect the number of mosquitos set at beginning of script TODO: fix this.
        # number_infected = 0
        # while number_infected < mosquito_init_infectd:
        #   for x in vector_population:
        #        if random.uniform(0, 1) < .01:
        #            vector_population[x]['infected'] = 'True'
        #            vector_population[x]['susceptible'] = 'False'
        #            vector_population[x]['exposed'] = 'False'

        #           number_infected += 1

        subregions_list.append(vector_population)
        count += 1

    return subregions_list


def shape_subregions(wd):
    """
    Read CSV
    :param filename: CSV filename
    :return: Dict of subregions
    """

    sub_list = subregion_list_of_lists_generators(wd)

    return sub_list


def writer(filename, line):
    """
    Write data to CSV, line by line
    :param filename: CSV file to write to
    :param line: Line to write
    :return:
    """

    with open(filename, 'a', newline='') as csvfile:
        writer = csv.writer(csvfile, delimiter=',')
        writer.writerow(line)


def check_if_file_exists(file):
    """
    Checks if file exists and prompts user for action
    :param file: File path
    :return:
    """

    if os.path.isfile(file):
        if prompt("File {0} exists: overwrite?".format(file)):
            try:
                os.remove(file)
            except OSError:
                raise OSError

        # Create backup of file if it already exists
        elif prompt("Create backup of {0} named {1}? ".format(file, file + '.bk')):
            new_file = file + '.bk'
            os.rename(file, new_file)

        else:
            print("Take care of existing files and try again. I'm leaving you. Bye.")
            die()


def output_status(n, total):
    """
    Gets percentage of file output to print to screen
    :param n:
    :param total:
    :return:
    """

    return (n / total) * 100


def build_population_files(directory, tableToBuild):  #TODO: This needs to be refactored
    global session

    uuidList = []
    infectList = []
    importer_list = []

    try:

        if tableToBuild == 'Humans':
            logger.info("Building host population.")

            # Print population structure info
            population = (build_population())

            pregnancy_eligible = 0
            pregnant_count = 0

            print("Creating population tables for database...")

            for dictionary in population:  # Human dictionary
                for i in dictionary:
                    uniqueID = dictionary[i].get('uuid')
                    subregion = dictionary[i].get('subregion')
                    linkedTo = dictionary[i].get('linkedTo')
                    importer = dictionary[i].get('importer')
                    importDay = dictionary[i].get('importDay')
                    age = dictionary[i].get('age')
                    sex = dictionary[i].get('sex')
                    pregnant = dictionary[i].get('pregnant')
                    susceptible = dictionary[i].get('susceptible')
                    exposed = dictionary[i].get('exposed')
                    infected = dictionary[i].get('infected')
                    recovered = dictionary[i].get('recovered')
                    dayOfInf = dictionary[i].get('dayOfInf')
                    dayOfExp = dictionary[i].get('dayOfExp')
                    x = dictionary[i].get('x')
                    y = dictionary[i].get('y')

                    if sex == "Female":
                        if age >= 14 and age < 51:
                            pregnancy_eligible += 1
                    if pregnant == 'True':
                        pregnant_count += 1

                    if importer:
                        importer_list.append(i)

                    new_human = Humans(
                        uniqueID=uniqueID,
                        linkedTo=linkedTo,
                        subregion=subregion,
                        importer=importer,
                        importDay=importDay,
                        pregnant=pregnant,
                        susceptible=susceptible,
                        exposed=exposed,
                        infected=infected,
                        recovered=recovered,
                        dayOfInf=dayOfInf,
                        dayOfExp=dayOfExp,
                        geom='SRID=2845;POINT({0} {1})'.format(x, y)
                    )

                    uuidList.append(uniqueID)

                    del i
                    session.add(new_human)
                    del new_human

                session.commit()

            # Create initial human infections
            if initial_infected > 0:  # Only run if we start with human infections
                logger.info("Infecting {0} initial hosts.".format(initial_infected))
                initial_infection_counter = 0
                row_count = 1
                for i in range(initial_infected):
                    infectList.append(random.choice(uuidList))  # Select random person, by id, to infect

                clear_screen()  # it's prettier
                # for i in infectList:
                while initial_infection_counter < initial_infected:
                    for h in infectList:  # For each ID in the infected list,
                        row = session.query(Humans).filter_by(
                            uniqueID=h)  # select a human from the table whose ID matches
                        for r in row:
                            print("Infected {0} of {1}".format(row_count, initial_infected))
                            if r.uniqueID in infectList:  # This might be redundant. I think ' if r.id == h'
                                row.update({"susceptible": 'False'}, synchronize_session='fetch')
                                row.update({"exposed": 'False'}, synchronize_session='fetch')
                                row.update({"infected": 'True'}, synchronize_session='fetch')
                                row.update({"recovered": 'False'}, synchronize_session='fetch')
                                initial_infection_counter += 1
                            row_count += 1

                        session.commit()

            if number_of_importers > 0:
                print("Setting up disease importers...")
                logger.info("Setting up disease importers.")
                importer_counter = 0  # If we're allowing random people to bring in disease from elsewhere

                for i in range(number_of_importers + 1):  # Select importers randomly
                    importer = random.randint(1, len(population))
                    while importer in infectList or importer in importer_list:  # Can't use already infected hosts
                        importer = random.randint(1, len(population))
                    importer_list.append(importer)

                for importer in importer_list:
                    while importer_counter < number_of_importers:
                        for importer in importer_list:
                            row = session.query(Humans).filter_by(id=importer)
                            for person in row:
                                importDay = random.randint(1, days_to_run)
                                row.update({'importer': True}, synchronize_session='fetch')
                                row.update({'importDay': importDay}, synchronize_session='fetch')

                            session.commit()
                        importer_counter += 1

            logger.info("Successfully built host population.")
            input("\nHuman population table successfully built. Press enter to return to main menu.")

        elif tableToBuild == 'Vectors':
            vector_uuidList = []
            clear_screen()
            print("Building vector population")
            logger.info("Setting up vector population.")
            sleep(5)

            vector = (build_vectors())

            clear_screen()
            print("Adding vectors to PostGIS database...")

            subregion_counter = 1
            number_of_subregions = len(vector)

            for dictionary in vector:
                number_of_vectors = len(dictionary)
                clear_screen()
                print("Adding {0} vectors for subregion {1} of {2} to database...".format(number_of_vectors,
                                                                                          subregion_counter,
                                                                                          number_of_subregions))
                for i in dictionary:
                    uniqueID = dictionary[i].get('uuid')
                    subregion = dictionary[i].get('subregion')
                    vector_range = dictionary[i].get('range')
                    alive = dictionary[i].get('alive')
                    birthday = dictionary[i].get('birthday')
                    lifetime = dictionary[i].get('lifetime')
                    susceptible = dictionary[i].get('susceptible')
                    infected = dictionary[i].get('infected')
                    removed = dictionary[i].get('removed')
                    x = dictionary[i].get('x')
                    y = dictionary[i].get('y')

                    new_vector = Vectors(
                        uniqueID=uniqueID,
                        subregion=subregion,
                        vector_range=vector_range,
                        alive=alive,
                        birthday=birthday,
                        lifetime=lifetime,
                        susceptible=susceptible,
                        infected=infected,
                        removed=removed,
                        geom='SRID=2845;POINT({0} {1})'.format(x, y)
                    )

                    vector_uuidList.append(uniqueID)

                    session.add(new_vector)
                session.commit()
                subregion_counter += 1

            # Create initial vector infections
            if mosquito_init_infectd > 0:  # Only run if we start with mosquito infections
                logger.info("Infecting {0} initial vectors.".format(mosquito_init_infectd))
                initial_infection_counter = 0
                infectList = []
                row_count = 1
                for i in range(mosquito_init_infectd):
                    infectList.append(random.choice(vector_uuidList))  # Select random person, by id, to infect

                clear_screen()  # it's prettier
                # for i in infectList:
                while initial_infection_counter < mosquito_init_infectd:
                    for h in infectList:  # For each ID in the infected list,
                        row = session.query(Vectors).filter_by(
                            uniqueID=h)  # select a human from the table whose ID matches
                        for r in row:
                            print("Infected {0} of {1} vectors".format(row_count, mosquito_init_infectd))
                            if r.uniqueID in infectList:  # This might be redundant. I think ' if r.id == h'
                                row.update({"susceptible": 'False'}, synchronize_session='fetch')
                                row.update({"infected": 'True'}, synchronize_session='fetch')
                                initial_infection_counter += 1
                            row_count += 1

                        session.commit()

            del vector[:]

            logger.info("Successfully built vector population.")
            input("Vector population table successfully built. Press enter to return to main menu.")

    except KeyboardInterrupt:
        input("You interrupted me! Press enter to return to main menu.")
        main_menu()


def build_range_links():
    """
    Adds rows to links table based on host distance from vector
    """

    clear_screen()
    print("\nLoading host database into RAM...")
    logger.info("Loading host database into ram, for building range links.")
    row = session.query(Humans).yield_per(1000)  # This might be way more efficient
    population = dict(
        (r.id, {
            'id': r.id,
            'x': r.x,
            'y': r.y
        }) for r in row
    )

    print("Loading vector database into RAM...")
    logger.info("Loading vector database into ram, for building range links.")
    vectors = session.query(Vectors).yield_per(1000)
    vectors = dict(
        (v.id, {
            'id': v.id,
            'range': v.vector_range,
            'x': v.x,
            'y': v.y
        }) for v in vectors
    )

    print("Linking...")
    logger.info("Attempting to build vector-host range links.")
    for vector in vectors:
        vector_id = vectors.get(vector)['id']
        vector_range = vectors.get(vector)['range']  # These may need some work
        vector_x = float(vectors.get(vector)['x'])
        vector_y = float(vectors.get(vector)['y'])

        vector_coordinates = [vector_x, vector_y]

        for human in population:
            human_id = population.get(human)['id']
            human_x = float(population.get(human)['x'])
            human_y = float(population.get(human)['y'])

            human_coordinates = [human_x, human_y]

            if euclidian(vector_coordinates,
                         human_coordinates) < vector_range:  # Add the relationship to the link table
                distance = euclidian(vector_coordinates, human_coordinates)

                new_link = vectorHumanLinks(
                    human_id=human_id,
                    vector_id=vector_id,
                    distance=distance
                )

                session.add(new_link)
    logger.info("Successfully built vector-host range links. Committing to PostGIS.")
    session.commit()


def euclidian(a, b):
    """
    Calculate distance between points on 2d surface
    :param a: a list of coordinates for point a
    :param b: a list of coordinates for point b
    :return: distance in whichever unit is provided to the function
    """

    x1 = a[0]
    y1 = a[1]

    x2 = b[0]
    y2 = b[1]

    a = np.array((x1, y1))
    b = np.array((x2, y2))

    dist = np.linalg.norm(a - b)

    return dist


def simulation():  #TODO: This needs to be refactored.
    """
    Simulation class
    :return:
    """

    # TODO: Create backup_table function and use here.
    # TODO: Auto end simulation if infections end
    # TODO: Fix total exposed counter


    rowNum = 1
    day = 0
    converged = False
    id_list = []
    subregion_list = []
    number_humans = session.query(Humans).count()
    initial_susceptible_humans = session.query(Humans).filter_by(susceptible='True').count()
    initial_susceptible_vectors = session.query(Vectors).filter_by(susceptible='True').count()
    nInfectedVectors = 1
    nSuscVectors = 1
    number_vectors = session.query(Vectors).count()
    total_exposed = 0

    clear_screen()

    try:
        setupDB()
    except NameError:
        logger.error("Simulation was started with no database loaded.")
        input("Database not loaded. Press enter to return to main menu.")
        main_menu()

    if days_to_run >= 365:
        print("Currently running simulation. This will take a while. \nGrab some coffee and catch up on some reading.")
        logger.info("Beginning simulation - for {} days.".format(days_to_run))

    print("\nLoading host population data...")
    row = session.query(Humans).yield_per(1000)  # This might be way more efficient
    population = dict(
        (r.id, {
            'id': r.id,
            'uniqueID': r.uniqueID,
            'subregion': r.subregion,
            'linkedTo': r.linkedTo,
            'importer': r.importer,
            'importDay': r.importDay,
            'pregnant': 'False',
            'susceptible': r.susceptible,
            'infected': r.infected,
            'exposed': r.exposed,
            'recovered': r.recovered,
            'dayOfInf': r.dayOfInf,
            'dayOfExp': r.dayOfExp,
            'biteCount': 0,
            'contacts': 0
        }) for r in row
    )

    logger.info("Successfully loaded host population data.")

    for p in population:
        subregion = population.get(p)['subregion']

        if subregion not in subregion_list:
            subregion_list.append(subregion)

        id_list.append(population.get(p)['id'])

    print("Loading vector population data...")
    vectors = session.query(Vectors).yield_per(1000)
    vectors = dict(
        (v.id, {
            'id': v.id,
            'uniqueID': v.uniqueID,
            'alive': v.alive,
            'daysAlive': 0,
            'birthday': v.birthday,
            'lifetime': v.lifetime,
            'subregion': v.subregion,
            'susceptible': v.susceptible,
            'infected': v.infected,
            'removed': v.removed
        }) for v in vectors
    )

    logger.info("Successfully loaded vector population data.")
    logger.info("Beginning simulation loop.")

    print("Running simulation...")

    vector_list = []
    for v in vectors:
        vector_list.append(v)

    relationship_infected_list = []

    try:
        while day < days_to_run and converged == False:

            biteable_humans = number_humans
            exposed_count = 0
            infected_count = 0
            recovered_count = 0
            vector_susceptible_count = 0
            vector_infected_count = 0
            vector_removed_count = 0

            if day == 0:  # Start log at day 0
                susceptible_count = session.query(Humans).filter(Humans.susceptible == 'True').count()
                log_entry = Log(Day=day,
                                nSusceptible=initial_susceptible_humans,
                                nExposed=exposed_count,
                                nInfected=infected_count,
                                nRecovered=recovered_count,
                                nDeaths=0,
                                nBirthInfections=0,
                                nInfectedVectors=vector_infected_count,
                                nSuscVectors=initial_susceptible_vectors,
                                nRemovedVectors=vector_removed_count)
                session.add(log_entry)
                session.commit()

            susceptible_count = 0

            # Run human-human interactions
            for r in id_list:
                population.get(r)['contacts'] = 0  # Reset contact counter each day
                person_a = population.get(r)
                contact_counter = 0
                person_a['biteCount'] = 0

                if person_a['susceptible'] == 'True':
                    if person_a['importDay'] == day:
                        choices = ["infected", "exposed"]
                        choice = random.choice(choices)
                        person_a[choice] = 'True'
                        person_a['susceptible'] = 'False'

                if person_a['uniqueID'] in relationship_infected_list and person_a['susceptible'] == 'True':
                    if random.uniform(0, 1) < kappa:
                        relationship_infected_list.remove(person_a['uniqueID'])  # TODO: Add random number gen
                        person_a['susceptible'] = 'False'
                        person_a['exposed'] = 'True'

                if person_a['exposed'] == 'True':
                    if person_a['dayOfExp'] >= latent_period:
                        person_a['exposed'] = 'False'
                        person_a['infected'] = 'True'

                if person_a['infected'] == 'True':
                    if person_a['dayOfInf'] >= infectious_period:
                        if causes_death:
                            person_a['infected'] = 'False'
                            if random.uniform(0, 1) < death_chance:
                                person_a['dead'] = 'True'

                            else:
                                person_a['recovered'] = 'True'
                                person_a['infected'] = 'False'

                        else:
                            person_a['infected'] = 'False'
                            person_a['recovered'] = 'True'

                # This will only do something if the person is already infected
                if person_a['linkedTo'] and person_a['infected'] == 'True':
                    pid = person_a['linkedTo']  # Contact spouse

                    relationship_infected_list.append(pid)
            if day >= mosquito_season_start:
                for vector in vector_list:
                    if vectors.get(vector)['birthday'] == day and \
                                    vectors.get(vector)['alive'] == 'False' and \
                                    vectors.get(vector)['removed'] == 'False':  # Number of vectors varies each day
                        vectors.get(vector)['alive'] = 'True'
                        vectors.get(vector)['susceptible'] = 'True'

                    if vectors.get(vector)['daysAlive'] >= vectors.get(vector)['lifetime']:
                        vectors.get(vector)['removed'] = 'True'
                        vectors.get(vector)['alive'] = 'False'
                        vectors.get(vector)['susceptible'] = 'False'
                        vectors.get(vector)['infected'] = 'False'

                    if vectors.get(vector)['alive'] == 'True':
                        i = 0
                        bite_list = []
                        vector_contacts = session.query(vectorHumanLinks).filter_by(
                            vector_id=vectors.get(vector)["uniqueID"])
                        for bite in vector_contacts:
                            host = session.query(Humans).filter_by(uniqueID=bite.human_id)
                            for human in host:
                                bite_list.append(human.id)

                        if len(bite_list) > 0:
                            while i < biting_rate and biteable_humans > 0:
                                bite = random.choice(bite_list)

                                if population.get(bite)['susceptible'] == 'True' and vectors.get(vector)[
                                    'infected'] == 'True':
                                    if random.uniform(0, 1) < beta:
                                        population.get(bite)['exposed'] = 'True'
                                        population.get(bite)['susceptible'] = 'False'

                                elif population.get(bite)['infected'] == 'True' and vectors.get(vector)[
                                    'susceptible'] == 'True':
                                    print('infected a vector')
                                    vectors.get(vector)['infected'] = 'True'
                                    vectors.get(vector)['susceptible'] = 'False'

                                population.get(bite)['biteCount'] += 1
                                i += 1

            for person in id_list:  # Get the count for each bin, each day.
                if population.get(person)['susceptible'] == 'True':
                    susceptible_count += 1

                elif population.get(person)['exposed'] == 'True':
                    exposed_count += 1
                    population.get(person)['dayOfExp'] += 1

                elif population.get(person)['infected'] == 'True':
                    infected_count += 1
                    population.get(person)['dayOfInf'] += 1

                elif population.get(person)['recovered'] == 'True':
                    recovered_count += 1

            for v in vector_list:
                if vectors.get(v)['alive'] == 'True':
                    vectors.get(v)['daysAlive'] += 1

                if vectors.get(v)['susceptible'] == 'True':
                    vector_susceptible_count += 1

                if vectors.get(v)['alive'] == 'True':
                    if vectors.get(v)['infected'] == 'True':
                        vector_infected_count += 1

                elif vectors.get(v)['removed'] == 'True':
                    vector_removed_count += 1

            clear_screen()
            print("Epidemiological Model Running\n")
            print("Simulating day {0} of {1}".format(day, days_to_run))
            print("\n--------------------------------"
                  "\nSusceptible hosts:    {0}     "
                  "\nExposed hosts:        {1}     "
                  "\nInfected hosts:       {2}     "
                  "\nRecovered hosts:      {3}     "
                  "\n================================"
                  "\nSusceptible vectors:  {4}     "
                  "\nInfected vectors:     {5}     "
                  "\nRemoved vectors:      {6}     "
                  "\n--------------------------------"
                  .format(susceptible_count, exposed_count, infected_count, recovered_count,
                          vector_susceptible_count, vector_infected_count, vector_removed_count))

            log_entry = Log(Day=day + 1,
                            subregion=None,
                            nSusceptible=susceptible_count,
                            nExposed=exposed_count,
                            nInfected=infected_count,
                            nRecovered=recovered_count,
                            nDeaths='0',
                            nBirthInfections='0',
                            nInfectedVectors=vector_infected_count,
                            nSuscVectors=vector_susceptible_count,
                            nRemovedVectors=vector_removed_count)
            session.add(log_entry)
            day += 1

            #if vector_infected_count == 0 and
        logger.info("Committing log to PostGIS.")
        session.commit()

        not_exposed = session.query(Humans).filter_by(susceptible='True').count()
        clear_screen()
        print("**Post-epidemic Report**\n\n"
              "- Total Days Run: {0}\n"
              "- Total Exposed: {1}\n"
              "- Average Exposed/Day: {2}\n"
              "- Population Not Exposed: {3}\n".format(days_to_run,
                                                       total_exposed,
                                                       round((number_humans - not_exposed / days_to_run), 2),
                                                       not_exposed))

        # Update the log entry for the day. Might want to build in a dictionary first and then
        # update the table at end of simulation.

        logger.info("Simulation complete.")
        input("\nPress enter to return to main menu.")

    except KeyboardInterrupt:
        session.commit()
        clear_screen()
        input("You interrupted me. Going back to main menu.")
        main_menu()


def subregion_list_of_lists_generators(wd):
    """
    Generates random points based on coordinates and subregion DI
    """
    records = point_creator.grab_vertices(wd + '/subregions')  # Load subregions shapefile
    # TODO:  Create function to iterate through subregion ids, create points, and feed them to the point_in_poly

    return records


def setupDB():
    """
    Set up the sqlite DB
    :return: a sqlalchemy session
    """

    global working_directory
    global working_directory_set
    global session

    logger.info("Loading data from PostGIS.")
    # engine = create_engine('sqlite:///simulation.epi')
    engine = create_engine('postgresql://simulator:Rward0232@localhost/simulation')
    DBSession = sessionmaker(bind=engine)
    session = DBSession()

    return session


def read_db():
    """
    Reads existing .epi db
    :return: A sqlalchemy session
    """

    global session, engine

    try:
        logger.info("Connecting to PostGIS database.")
        engine = create_engine('postgresql://simulator:Rward0232@localhost/simulation')

        metadata = MetaData(engine)
        population = Table('Humans', metadata, autoload=True)
        vectors = Table('vectors', metadata, autoload=True)

        # mapper(Humans, population)
        # mapper(Vectors, vectors)

        Session = sessionmaker(bind=engine)
        session = Session()

        clear_screen()
        logger.info("Connected to PostGIS database.")
        input("\n\nSuccessfully connected to database. Press enter to return to the main menu.")

        return session

    except:
        logger.error("Could not load database.")
        clear_screen()
        input("Could not load database. Make sure the database is called 'simulation.epi.' Unfortunately, you may need"
              "to rebuild it. Press enter to return to the main menu.")
        main_menu()


def drop_table(table_drop):
    """
    Drops whichever table is wanted from the DB
    :param table_drop: A string defining table to drop.
    :return:
    """

    try:
        dbPath = 'simulation.epi'
        engine = create_engine('sqlite:///%s' % dbPath, echo=False)

        metadata = MetaData(engine)

        Session = sessionmaker(bind=engine)
        session = Session()

        if table_drop == 'Humans':
            logger.info("Dropped host population table.")
            population = Table('Humans', metadata, autoload=True)
            population.drop(engine)
            setupDB()

        elif table_drop == 'Vectors':
            logger("Droped vector population table.")
            population = Table('Vectors', metadata, autoload=True)
            population.drop(engine)
            setupDB()

        else:
            input("I did something weird. Press enter to return to main menu.")
            main_menu()

        clear_screen()
        input("\n\nSuccessfully drooped table '{0}'. Press enter to return to the main menu.".format(table_drop))

    except:
        clear_screen()
        input("Could not droptable. Make sure database is named 'simulation.epi,' and that it is loaded."
              "Press enter to return to main menu.")
        main_menu()


def create_config_file():
    """
    Prompts user for settings and creates configuration file using configparser
    :return:
    """
    # Flags for menu
    simulation_parameters_set = 'Not Set'
    host_population_settings_set = 'Not Set'
    vector_population_settings_set = 'Not Set'
    disease_parameters_set = 'Not Set'
    config = configparser.ConfigParser()

    global working_directory

    while True:
        try:
            """Main menu for program. Prompts user for function."""
            clear_screen()
            print("Python Epidemiological Model\n\n"
                  "Simulation Settings\n"
                  "1. Simulation Parameters - {0}\n"
                  "2. Host Population Parameters - {1}\n"
                  "3. Vector Population Parameters - {2}\n"
                  "4. Disease Parameters - {3}\n"
                  "5. Write Config File\n"
                  "6. Read ESRI Shapefile\n"
                  "7. Main Menu\n".format(simulation_parameters_set,
                                          host_population_settings_set,
                                          vector_population_settings_set,
                                          disease_parameters_set))

            answer = input(">>> ")

            if answer.startswith('1'):
                clear_screen()
                print("***Python Epidemiological Model***\n"
                      "Simulation Parameters\n")

                config['SIMULATION PARAMETERS'] = {
                    'RandomSeed': input("Random seed: "),
                    'DaysToRun': input("Days to run simulation: "),
                    'Seasonality': prompt("Seasonality in vector poulation?: ")
                }

                simulation_parameters_set = 'Set'

            if answer.startswith('2'):
                clear_screen()
                print("***Python Epidemiological Model***\n"
                      "Host Population Parameters\n")

                config["HOST POPULATION PARAMETERS"] = {
                    'initial_exposed': input("Number of hosts to expose before model begins: "),
                    'initial_infected': input("Number of hosts to infect before model begins: "),
                    'contact_rate': input("Number of contacts per day, per host: "),
                    'imports': prompt("Allow individuals to import disease from elsewhere?"),
                    'nImporters': input("If so, how many importers?: "),
                    'bite_limit': input("How many times is each host allowed to be bitten by a mosquito per day?: ")
                }

                host_population_settings_set = 'Set'

            if answer.startswith('3'):
                clear_screen()
                print("***Python Epidemiological Model***\n"
                      "Vector Population Parameters\n")

                config['VECTOR POPULATION PARAMETERS'] = {
                    'mosquito_susceptible_coef': input("Mosquitos per square kilometer: "),
                    'mosquito_exposed': input("Number of vectors to expose before model begins: "),
                    'mosquito_init_infected': input("Number of vectors to infect before model begins: "),
                    'biting_rate': input("Number of humans each mosquito bites per day: "),
                    'season_start': input("What day will mosquito season begin?: "),
                    'season_end': input("What day will mosquito season end?: ")
                }

                vector_population_settings_set = 'Set'

            if answer.startswith('4'):
                clear_screen()
                print("***Python Epidemiological Model***\n"
                      "Epidemic Parameters\n")

                config['EPIDEMIC PARAMETERS'] = {
                    'causes_death': prompt("Can disease end in death?"),
                    'death_chance': input("If disease can cause death, what is the probability (0-1)?: "),
                    'beta': input("What is the beta value (probability of infection)?: "),
                    'gamma': input("What is the gamma value (Rate at which infected moves to recovery)?: "),
                    'sigma': input("What is the sigma value (Rate at which an exposed person becomes infective)?: "),
                    'mu': input("What is the mu value (Natural mortality rate)?: "),
                    'theta': input("What is the theta value (perinatal transmission rate)?: "),
                    'kappa': input("What is the kappa value (sexual contact transmission rate)?: "),
                    'zeta': input("What is the zeta value (transfusion transmission rate)?: "),
                    'tau': input("What is the tau value (human to vector transmission rate)?: "),
                    'infectious_period': input("How long is the disease infectious period, in days?: "),
                    'latent_period': input("How long is the disease latent period, in days?: ")
                }

                disease_parameters_set = 'Set'

            if answer.startswith('5'):
                with open('simulation.cfg', 'a') as configfile:
                    config.write(configfile)

            if answer.startswith('6'):
                if not working_directory_set:
                    working_directory = input("Working directory (All files must be in this path): ")

                subregion_list_of_lists_generators(working_directory)

            if answer.startswith('6'):
                main_menu()

        except KeyboardInterrupt:
            main_menu()


def read_config_section(section, bool):
    "Read section of file using configparser"
    config_dict = {}
    options = config.options(section)

    for option in options:
        if bool:
            try:
                config_dict[option] = config.getboolean(section, option)
            except:
                print("Exception on {}".format(option))
                config_dict = None
            return config_dict

        else:
            try:
                config_dict[option] = config.get(section, option)
            except:
                print("Exception on {}".format(option))
                config_dict = None

            return config_dict


def read_config_file():
    """
    Reads configuration file
    :return:
    """

    config.read('simulation.cfg')

    # Simulation parameters
    days_to_run = read_config_section('SIMULATION PARAMETERS', False)['daystorun']
    random_seed = read_config_section('SIMULATION PARAMETERS', False)['randomseed']
    seasonality = read_config_section('SIMULATION PARAMETERS', True)['seasonality']

    # Epidemic parameters
    causes_death = read_config_section("EPIDEMIC PARAMETERS", True)['causes_death']
    death_chance = read_config_section("EPIDEMIC PARAMETERS", False)['death_chance']
    latent_period = read_config_section("EPIDEMIC PARAMETERS", False)['latent_period']
    kappa = read_config_section("EPIDEMIC PARAMETERS", False)['kappa']
    sigma = read_config_section("EPIDEMIC PARAMETERS", False)['sigma']
    theta = read_config_section("EPIDEMIC PARAMETERS", False)['theta']
    gamma = read_config_section("EPIDEMIC PARAMETERS", False)['gamma']
    mu = read_config_section("EPIDEMIC PARAMETERS", False)['mu']
    infectious_period = read_config_section("EPIDEMIC PARAMETERS", False)['beta']
    beta = read_config_section("EPIDEMIC PARAMETERS", True)['causes_death']
    zeta = read_config_section("EPIDEMIC PARAMETERS", False)['zeta']
    tau = read_config_section("EPIDEMIC PARAMETERS", False)['tau']
    infectious_period = read_config_section("EPIDEMIC PARAMETERS", False)['infectious_period']
    latent_period = read_config_section("EPIDEMIC PARAMETERS", False)['latent_period']

    # Host population parameters
    initial_exposed = read_config_section("HOST POPULATION PARAMETERS", False)['initial_exposed']
    initial_infected = read_config_section("HOST POPULATION PARAMETERS", False)['initial_infected']
    contact_rate = read_config_section("HOST POPULATION PARAMETERS", False)['contact_rate']
    number_of_importers = read_config_section("HOST POPULATION PARAMETERS", False)['number_of_importers']
    bite_limit = read_config_section("HOST POPULATION PARAMETERS", False)['bite_limit']

    # Vector population parameters
    mosquito_susceptible_coef = read_config_section("VECTOR POPULATION PARAMETERS", False)['mosquito_susceptible_coef']

    mosquito_init_infectd = read_config_section("VECTOR POPULATION PARAMETERS", False)['mosquito_init_infected']

    biting_rate = read_config_section("VECTOR POPULATION PARAMETERS", False)['biting_rate']

    mosquito_exposed = read_config_section("VECTOR POPULATION PARAMETERS", False)['mosquito_exposed']

    season_start = read_config_section("VECTOR POPULATION PARAMETERS", False)['season_start']

    season_end = read_config_section("VECTOR POPULATION PARAMETERS", False)['season_end']


def config_menu():
    """
    Menu to call configuration methods
    :return:
    """

    global config
    global working_directory
    global working_directory_set
    config = configparser.ConfigParser()

    while True:
        try:
            """Main menu for program. Prompts user for function."""
            clear_screen()
            print("Python Epidemiological Model\n\n"
                  "What would you like to do?\n"
                  "1. Create configuration\n"
                  "2. Load configuration\n"
                  "3. Load existing tables\n"
                  "4. Build host table\n"
                  "5. Build vector table\n"
                  "6. Build vector-human range links\n"
                  "7. Plot vector-human bigraph\n"
                  "8. Main menu\n")

            answer = input(">>> ")

            if answer.startswith('1'):
                create_config_file()

            if answer.startswith('2'):
                session = read_config_file()

            if answer.startswith('3'):
                read_db()

            if answer.startswith('4'):
                if not working_directory_set:
                    working_directory = input("Path to shape data: ")
                    working_directory_set = True
                setupDB()

                build_population_files(working_directory, 'Humans')

            if answer.startswith('5'):
                if not working_directory_set:
                    working_directory = input("Path to shape data: ")
                    working_directory_set = True
                setupDB()

                build_population_files(working_directory, 'Vectors')

            if answer.startswith('6'):
                setupDB()
                build_range_links()

            if answer.startswith('7'):
                setupDB()
                create_graph()

            if answer.startswith('8'):
                main_menu()

        except KeyboardInterrupt:
            main_menu()


def main_menu():
    """
    The main menu of options
    :return:
    """

    logger.info("Program started.")

    working_directory_set = False

    while True:
        try:
            """Main menu for program. Prompts user for function."""
            clear_screen()
            print("Python Epidemiological Model\n\n"
                  "What would you like to do?\n"
                  "1. Configure Simulation\n"
                  "2. Run Simulation\n"
                  "3. Quit\n")

            answer = input(">>> ")

            if answer.startswith('1'):
                config_menu()

            if answer.startswith('2'):
                simulation()

            if answer.startswith('3'):
                logger.info("User killed program.")
                die()

        except KeyboardInterrupt:
            main_menu()


if __name__ == '__main__':
    main_menu()
