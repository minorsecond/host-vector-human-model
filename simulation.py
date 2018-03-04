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
from sqlalchemy import create_engine, MetaData, Table, and_
from sqlalchemy.orm import sessionmaker

from db import Humans, Vectors, Log, vectorHumanLinks
from gis import point_creator

global working_directory_set

working_directory_set = False

# Simulation parameters
DAYS_TO_RUN = 365
random.seed(5)

# Epidemic parameters
CAUSES_DEATH = False
DEATH_CHANCE = .001
BETA = 0.03
GAMMA = .3  # TODO: See how this interacts with infectious period.
SIGMA = .35  # TODO: See how this interacts with infectious period.
MU = .1
THETA = .1  # mother -> child transmission
BIRTHRATE = 0  # birth rate
KAPPA = .02  # sexual contact
ZETA = .1  # blood transfusion
TAU = .25  # chance a mosquito picks up zika from human
INFECTIOUS_PERIOD = 5
LATENT_PERIOD = 3

# Human population parameters
INITIAL_SUSCEPTIBLE = 750000  # Unused with subregions file
INITIAL_EXPOSED = 0
INITIAL_INFECTED = 5
CONTACT_RATE = 1
NUMBER_OF_IMPORTERS = 25  # number of people to bring back disease from foreign lands, over the study period
BITE_LIMIT = 3  # Number of bites per human, per day.

# Vector population parameters
GM_FLAG = False
MOSQUITO_SUSCEPTIBLE_COEF = 500  # mosquitos per square kilometer
MOSQUITO_EXPOSED = 0
MOSQUITO_INIT_INFECTED = 100  # 0
BITING_RATE = 3  # average bites per day
MOSQUITO_SEASON_START = 1  #78
MOSQUITO_SEASON_END = 266

# Set up logging
logger = logging.getLogger("epiSim")
logger.setLevel(logging.INFO)
fh = logging.FileHandler("epiSim.log")
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
logger.addHandler(fh)


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
        lifetime = random.gauss(3, .5)
    else:
        lifetime = random.gauss(15, 2)

    return lifetime


def build_vectors():
    """
    Builds vector population
    :return: Dict of dicts N size, with parameters
    """

    global GM_FLAG

    subregions_list = []
    count = 0
    infected_vectors = 0
    mosquito_season = list(range(MOSQUITO_SEASON_START, MOSQUITO_SEASON_END))

    in_subregion_data = os.path.join(working_directory)
    sub_regions_dict = sub_regions_dict = shape_subregions(in_subregion_data)

    # Flag for adding modified mosquitos to population.
    if GM_FLAG:
        modified = True
    else:
        modified = False

    for i in sub_regions_dict:
        subregion = i['id']  # subregion ID
        area = float(i['area'])  # get area from dict
        vector_pop = int((area / 1000000) * MOSQUITO_SUSCEPTIBLE_COEF)  # sq. meters to square km

        clear_screen()
        print("Building {0} vectors for subregion {1} of {2}".format(vector_pop, count, len(sub_regions_dict)))

        vector_population = dict(
            (x, {
                # 'uuid': str(uuid()),
                'subregion': subregion,
                'modified': modified,
                'range': random.gauss(90, 2),  # 90 meters or so
                'alive': 'False',  # They come to life on their birthdays
                'birthday': random.choice(mosquito_season),
                'lifetime': vector_lifetime(GM_FLAG),  # in days
                'susceptible': 'False',
                'exposed': 'False',
                'infected': 'False',
                'removed': 'False',
                'x': random_points(i)[0],
                'y': random_points(i)[1]
            }) for x in range(vector_pop)
        )

        # Infect the number of mosquitos set at beginning of script TODO: fix this.
        for vector in range(MOSQUITO_INIT_INFECTED):
            for x in vector_population:
                if random.uniform(0, 1) < .01:
                    vector_population[x]['infected'] = 'False'
                    vector_population[x]['susceptible'] = 'False'
                    vector_population[x]['exposed'] = 'False'

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
            if INITIAL_INFECTED > 0:  # Only run if we start with human infections
                logger.info("Infecting {0} initial hosts.".format(INITIAL_INFECTED))
                initial_infection_counter = 0
                row_count = 1
                for i in range(INITIAL_INFECTED):
                    infectList.append(random.choice(uuidList))  # Select random person, by id, to infect

                clear_screen()  # it's prettier
                # for i in infectList:
                while initial_infection_counter < INITIAL_INFECTED:
                    for h in infectList:  # For each ID in the infected list,
                        row = session.query(Humans).filter_by(
                            uniqueID=h)  # select a human from the table whose ID matches
                        for r in row:
                            print("Infected {0} of {1}".format(row_count, INITIAL_INFECTED))
                            if r.uniqueID in infectList:  # This might be redundant. I think ' if r.id == h'
                                row.update({"susceptible": 'False'}, synchronize_session='fetch')
                                row.update({"exposed": 'False'}, synchronize_session='fetch')
                                row.update({"infected": 'True'}, synchronize_session='fetch')
                                row.update({"recovered": 'False'}, synchronize_session='fetch')
                                initial_infection_counter += 1
                            row_count += 1

                        session.commit()

            if NUMBER_OF_IMPORTERS > 0:
                print("Setting up disease importers...")
                logger.info("Setting up disease importers.")
                importer_counter = 0  # If we're allowing random people to bring in disease from elsewhere

                for i in range(NUMBER_OF_IMPORTERS + 1):  # Select importers randomly
                    importer = random.randint(1, len(population))
                    while importer in infectList or importer in importer_list:  # Can't use already infected hosts
                        importer = random.randint(1, len(population))
                    importer_list.append(importer)

                for importer in importer_list:
                    while importer_counter < NUMBER_OF_IMPORTERS:
                        for importer in importer_list:
                            row = session.query(Humans).filter_by(id=importer)
                            for person in row:
                                importDay = random.randint(1, DAYS_TO_RUN)
                                row.update({'importer': True}, synchronize_session='fetch')
                                row.update({'importDay': importDay}, synchronize_session='fetch')

                            session.commit()
                        importer_counter += 1

            logger.info("Successfully built host population.")
            input("\nHuman population table successfully built. Press enter to return to main menu.")

        elif tableToBuild == 'Vectors':

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

                    session.add(new_vector)
                session.commit()
                subregion_counter += 1
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
    #id_list = []
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

    if DAYS_TO_RUN >= 365:
        print("Currently running simulation. This will take a while. \nGrab some coffee and catch up on some reading.")
        sleep(3)
        logger.info("Beginning simulation - for {} days.".format(DAYS_TO_RUN))

    rows = session.query(Humans).yield_per(1000)  # This might be way more efficient

    #print("DEBUG: Parsing population data from dict.")
    population = dict(
        (r.id, {
            'id': r.id,
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
        }) for r in rows
    )

    #print("DEBUG: Done.")

    logger.info("Successfully loaded host population data.")

    for p in population:
        subregion = population.get(p)['subregion']

        if subregion not in subregion_list:
            subregion_list.append(subregion)

    vectors = session.query(Vectors).yield_per(1000)

    #print("DEBUG: Parsing vector data from dict.")
    vectors = dict(
        (v.id, {
            'id': v.id,
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

    #print("DEBUG: Done.")

    logger.info("Successfully loaded vector population data.")
    logger.info("Beginning simulation loop.")

    try:
        while day < DAYS_TO_RUN and converged == False:  # TODO: Finish this next.
            print("initializing simulation")
            for subregion in subregion_list:
                biteable_humans = number_humans
                susceptible_count = 0
                exposed_count = 0
                infected_count = 0
                recovered_count = 0
                vector_list = []
                id_list = []
                vector_susceptible_count = 0
                vector_infected_count = 0
                vector_removed_count = 0

                print("DEBUG: Parsing subregion population..")
                for p in population:
                    if population.get(p)['subregion'] == subregion:
                        id_list.append(p)

                print("DEBUG: Parsing subregion vector population..")
                for v in vectors:
                    if vectors.get(v)['birthday'] == day and \
                                    vectors.get(v)['alive'] == 'False' and \
                                    vectors.get(v)['removed'] == 'False':  # Number of vectors varies each day
                        vectors.get(v)['alive'] = 'True'
                        vectors.get(v)['susceptible'] = 'True'
                    vector_list.append(v)  # TODO: Find a way to deal with this as it makes the sim slow.

                print("DEBUG: Starting the simulation")
                if day == 0:  # Start log at day 0
                    susceptible_count = session.query(Humans).filter(and_(Humans.susceptible == 'True',
                                                                             Humans.subregion == subregion)).count()
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

                # Run human-human interactions
                print("DEBUG: Simulating contacts between {0} humans and {1} vectors".format(len(id_list),
                                                                                             len(vector_list)))
                for r in id_list:

                    population.get(r)['contacts'] = 0  # Reset contact counter each day

                    if population.get(r)['subregion'] == subregion:
                        person_a = population.get(r)
                        contact_counter = 0
                        person_a['biteCount'] = 0

                        if person_a['susceptible'] == 'True':
                            if person_a['importDay'] == day:
                                choices = ["infected", "exposed"]
                                choice = random.choice(choices)
                                person_a[choice] = 'True'
                                person_a['susceptible'] = 'False'
                                print("Disease imported into {}!".format(subregion))

                        if person_a['exposed'] == 'True':
                            if person_a['dayOfExp'] >= LATENT_PERIOD:
                                person_a['exposed'] = 'False'
                                person_a['infected'] = 'True'
                                print("Someone became infected in {}!".format(subregion))

                        if person_a['infected'] == 'True':
                            if person_a['dayOfInf'] >= INFECTIOUS_PERIOD:
                                if CAUSES_DEATH:
                                    person_a['infected'] = 'False'
                                    if random.uniform(0, 1) < DEATH_CHANCE:
                                        person_a['dead'] = 'True'
                                        print("Someone died in {}!".format(subregion))

                                    else:
                                        person_a['recovered'] = 'True'
                                        person_a['infected'] = 'False'
                                        print("Someone recovered in {}!".format(subregion))

                                else:
                                    person_a['infected'] = 'False'
                                    person_a['recovered'] = 'True'
                                    print("Someone recovered in {}!".format(subregion))

                        while contact_counter < CONTACT_RATE:  # Infect by contact rate per day
                            # Choose any random number except the one that identifies the person selected, 'h'

                            if not population.get(r)['linkedTo']:  # Check if a value is set in the "linkedTo" field
                                pid = random.choice(id_list)

                                while pid == r or population.get(pid)[
                                    'linkedTo']:  # Can't infect theirself or linked spouse
                                    pid = random.choice(id_list)

                            else:
                                pid = population.get(r)['linkedTo']  # Contact spouse
                                #person_b = population.get(pid)
                                person_b = session.query(Humans).filter_by(uniqueID=pid).first()

                                #if person_b['contacts'] == 0:  # Make sure not doubling up on contacts each day

                                if person_a['infected'] == 'True':
                                    if random.uniform(0, 1) < KAPPA:  # chance of infection
                                        person_b.update({"exposed": 'True'}, synchronize_session='fetch')
                                        person_b.update({"susceptible": 'False'}, synchronize_session='fetch')
                                        total_exposed += 1
                                        print("Someone infected their spouse in {}!".format(subregion))

                                # the infection can go either way
                                elif person_b.infected == 'True':
                                    if random.uniform(0, 1) < KAPPA:  # chance of infection
                                        person_a['exposed'] = 'True'
                                        person_a['susceptible'] = 'False'
                                        total_exposed += 1
                                        print("Someone infected their spouse in {}!".format(subregion))

                            contact_counter += 1

                # Run mosquito-human interactions
                for v in vector_list:
                    i = 0
                    if vectors.get(v)['subregion'] == subregion:
                        vector = vectors.get(v)
                        if vector['alive'] == 'True':
                            while i < BITING_RATE and biteable_humans > 0:

                                pid = random.choice(id_list)  # Pick a human to bite
                                while population.get(pid)['subregion'] != subregion:
                                    pid = random.choice(id_list)
                                person = population.get(pid)

                                if person['susceptible'] == 'True' and vector['infected'] == 'True' and random.uniform(
                                        0, 1) < BETA:
                                    person['susceptible'] = 'False'
                                    person['exposed'] = 'True'
                                    print("DEBUG: We have a bite!!!")

                                elif person['infected'] == 'True' and vector[
                                    'susceptible'] == 'True':  # TODO: chance of vector infection
                                    vector['susceptible'] = 'False'
                                    vector['infected'] = 'True'
                                person['biteCount'] += 1

                                if person['biteCount'] >= BITE_LIMIT:
                                    biteable_humans -= 1
                            i += 1

                            if vector['daysAlive'] >= vector['lifetime']:
                                vector['removed'] = 'True'
                                vector['alive'] = 'False'
                                vector['susceptible'] = 'False'
                                vector['infected'] = 'False'

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

                    if vectors.get(v)['infected'] == 'True':
                        vector_infected_count += 1

                    elif vectors.get(v)['removed'] == 'True':
                        vector_removed_count += 1

                log_entry = Log(Day=day + 1,
                                subregion=subregion,
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

            clear_screen()
            print("Epidemiological Model Running\n")
            print("Simulating day {0} of {1}".format(day, DAYS_TO_RUN))
            print("\n---------------------------------"
                  "\nSusceptible hosts:    {0}     "
                  "\nExposed hosts:        {1}     "
                  "\nInfected hosts:       {2}     "
                  "\nRecovered hosts:      {3}     "
                  "\n================================="
                  "\nSusceptible vectors:  {4}     "
                  "\nInfected vectors:     {5}     "
                  "\nRemoved vectors:      {6}     "
                  "\n---------------------------------"
                  .format(susceptible_count, exposed_count, infected_count, recovered_count,
                          vector_susceptible_count, vector_infected_count, vector_removed_count))

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
              "- Population Not Exposed: {3}\n".format(DAYS_TO_RUN,
                                                       total_exposed,
                                                       round((number_humans - not_exposed / DAYS_TO_RUN), 2),
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
    engine = create_engine('postgresql://rwardrup:Rward0232@localhost/simulation')
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
        engine = create_engine('postgresql://rwardrup:Rward0232@localhost/simulation')

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


def clear_screen():
    """
    Clears the screen to keep output tidy
    :return:
    """

    os.system('cls' if os.name == 'nt' else 'clear')


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
                  "7. Main menu\n")

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
