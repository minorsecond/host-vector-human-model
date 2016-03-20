"""
2016 - Robert Ross Wardrup
A SEIR simulation that uses SQLite and CSV Census files to define population paramaters
Please run this on a rotating hard drive - building large
"""

# TODO: Use spatialite db to allow spatial analyses of results and perhaps random walk simulations for vectors
# TODO: Method to allow cross-subregion exposure (based off euclidian distance)
# TODO: Read and write config file
# TODO: Seasonal variations in mosquito population. Allow entry of day # where each season begins. Maybe use a sine.

import configparser
import csv
import os.path
import random
from sys import exit as die
from time import sleep
from uuid import uuid4 as uuid

import numpy as np
from sqlalchemy import create_engine, MetaData, Table
from sqlalchemy.orm import sessionmaker

from db import Humans, Vectors, Log

global working_directory_set
working_directory_set = False

# Simulation parameters
days_to_run = 365
random.seed(5)

# Epidemic parameters
causes_death = False
death_chance = .001
beta = 0.03
gamma = .3  # TODO: See how this interacts with infectious period.
sigma = .35  # TODO: See how this interacts with infectious period.
mu = .1
theta = .1  # mother -> child transmission
birthrate = 0  # birth rate
kappa = .02  # sexual contact
zeta = .1  # blood transfusion
tau = .25  # chance a mosquito picks up zika from human
infectious_period = 5
latent_period = 3

# Human population parameters
initial_susceptible = 750000  # Unused with subregions file
initial_exposed = 0
initial_infected = 1
contact_rate = 1
number_of_importers = 25  # number of people to bring back disease from foreign lands, over the study period
bite_limit = 3  # Number of bites per human, per day.

# Vector population parameters
mosquito_susceptible_coef = 500  # mosquitos per square kilometer
mosquito_exposed = 0
mosquito_init_infectd = 0
biting_rate = 3  # average bites per day
mosquito_season_start = 78
mosquito_season_end = 266


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
    Ray casting method of determining if point lies within a polygon. To be used for
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


def build_population():
    """
    Builds population with parameters
    :return: Dict of dicts N size, with parameters
    """

    subregions_list = []

    in_subregion_data = os.path.join(working_directory, 'subregions.csv')
    sub_regions_dict = sub_regions(in_subregion_data)
    clear_screen()
    print('- Building population for {0} sub-regions. This will take a second..'.format(len(sub_regions_dict) - 1))

    for i in sub_regions_dict:
        subregion = i  # subregion ID
        pop = sub_regions_dict[i].get('pop')  # grab population from subregion dict

        population = dict(
            (x, {
                'uuid': str(uuid()),
                'subregion': subregion,
                'importer': False,  # Brings disease in from another place
                'importDay': -999,
                'age': random.randint(0, 99),
                'sex': random.choice(['Male', 'Female']),
                'pregnant': 'False',
                'susceptible': 'True',
                'infected': 'False',
                'exposed': 'False',
                'recovered': 'False',
                'dayOfInf': 0,
                'dayOfExp': 0,
                # 'dayOfRec': 0,
                'recState': 0,
                'resistant': 'False',
                'x': np.random.uniform(689141.000, 737293.000),  # Extents for Tarrant county, TX
                'y': np.random.uniform(2098719.000, 2147597.000)

            }) for x in range(pop)
        )

        for x in population:  # assign pregnancy to some of population  This is duplicated.  TODO: figure out which one works
            if population[x].get('sex') == "Female":
                if population[x].get('age') >= 15 and population[x].get('age') < 51:
                    if random.randint(0, 100) < 4:
                        population[x]['pregnant'] = 'True'

        subregions_list.append(population)

    return subregions_list


def build_vectors():
    """
    Builds vector population
    :return: Dict of dicts N size, with parameters
    """
    subregions_list = []
    infected_vectors = 0
    # mosquito_season_start = int(input("Start day of mosquito season: "))
    # mosquito_season_end = int(input("End day of mosquito season: "))
    mosquito_season = range(mosquito_season_start, mosquito_season_end)

    in_subregion_data = os.path.join(working_directory, 'subregions.csv')
    sub_regions_dict = sub_regions(in_subregion_data)

    clear_screen()
    print('Building vector population for {0} sub-regions. This will take a second..'.format(len(sub_regions_dict)))

    for i in sub_regions_dict:
        subregion = i
        area = float(sub_regions_dict[i].get('area'))  # get area from dict
        vector_pop = int((area / 1000000) * mosquito_susceptible_coef)  # sq. meters to square km

        vector_population = dict(
            (x, {
                'uuid': str(uuid()),
                'subregion': subregion,
                # 'range': random.uniform(0, 500),  # 500 meters or so
                'alive': 'False',  # They come to life on their birthdays
                'birthday': random.choice(mosquito_season),
                'lifetime': random.normalvariate(15, 2),  # in days
                'susceptible': 'False',
                'exposed': 'False',
                'infected': 'False',
                'removed': 'False',
                'x': np.random.uniform(689141.000, 737293.000),  # Extents for Tarrant county, TX
                'y': np.random.uniform(2098719.000, 2147597.000)
            }) for x in range(vector_pop)
        )

        # Infect the number of mosquitos set at beginning of script TODO: fix this.
        for vector in range(mosquito_init_infectd):
            for x in vector_population:
                if np.random.uniform(0, 1) < .01:
                    vector_population[x]['infected'] = 'False'
                    vector_population[x]['susceptible'] = 'False'
                    vector_population[x]['exposed'] = 'False'

        subregions_list.append(vector_population)


    return subregions_list


def sub_regions(filename):
    """
    Read CSV
    :param filename: CSV filename
    :return: Dict of subregions
    """

    header = 0
    subregion = {}

    with open(filename, 'r') as csvfile:
        # Skip header
        has_header = csv.Sniffer().has_header(csvfile.read(1024))
        csvfile.seek(0)

        # Read the CSV
        reader = csv.reader(csvfile, delimiter=',')
        if has_header:
            next(reader)
        subregion = dict(
            (row[0], {
                'pop': int(row[1]),
                'area': row[2]
            }) for row in reader
        )

    return subregion


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

    # while header_count == 0:
    #    lineOut = ['Subregion ID:, Individual ID', 'Age', 'Sex', 'Pregnancy Status']
    #    header_count = 1
    #    writer(population_structure_file, lineOut)

    idList = []
    infectList = []
    importer_list = []

    try:

        if tableToBuild == 'Humans':

            population_structure_file = os.path.join(directory, 'human_population.csv')
            check_if_file_exists(population_structure_file)

            # Print population structure info
            population = (build_population())

            pregnancy_eligible = 0
            pregnant_count = 0

            for dictionary in population:  # Human dictionary
                for i in dictionary:
                    uniqueID = dictionary[i].get('uuid')
                    subregion = dictionary[i].get('subregion')
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
                    resistant = dictionary[i].get('resistant')
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
                        # uniqueID=uniqueID,
                        subregion=subregion,
                        importer=importer,
                        importDay=importDay,
                        # age=age,
                        #sex=sex,
                        pregnant=pregnant,
                        susceptible=susceptible,
                        exposed=exposed,
                        infected=infected,
                        recovered=recovered,
                        dayOfInf=dayOfInf,
                        dayOfExp=dayOfExp,
                        #dayOfRec=dayOfRec,
                        # resistant=resistant,
                        # x=x,
                        #y=y
                    )

                    session.add(new_human)
                session.commit()

            # Create initial human infections
            if initial_infected > 0:  # Only run if we start with human infections
                initial_infection_counter = 0
                row_count = 1
                for i in range(initial_infected):
                    infectList.append(random.randint(1, len(population)))  # Select random person, by id, to infect
                clear_screen()  # it's prettier
                print("- Infecting {0} individuals to start the simulation.".format(initial_infected))
                for i in infectList:
                    while initial_infection_counter < initial_infected:
                        for h in infectList:  # For each ID in the infected list,
                            row = session.query(Humans).filter_by(
                                id=h)  # select a human from the table whose ID matches
                            for r in row:
                                print("Infected {0} of {1}".format(row_count, initial_infected))
                                if r.id in infectList:  # This might be redundant. I think ' if r.id == h'
                                    row.update({"susceptible": 'False'}, synchronize_session='fetch')
                                    row.update({"exposed": 'False'}, synchronize_session='fetch')
                                    row.update({"infected": 'True'}, synchronize_session='fetch')
                                    row.update({"recovered": 'False'}, synchronize_session='fetch')
                                    initial_infection_counter += 1
                                row_count += 1

                            session.commit()

            if number_of_importers > 0:
                importer_counter = 0  # If we're allowing random people to bring in disease from elsewhere

                for i in range(number_of_importers + 1):  # Select importers randomly
                    importer = random.randint(1, len(population))
                    while importer in infectList:
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

            input("\nHuman population table successfully built. Press enter to return to main menu.")

        elif tableToBuild == 'Vectors':

            vector_structure_file = os.path.join(directory, 'vector_population.csv')
            check_if_file_exists(vector_structure_file)

            clear_screen()
            print("Building vector population")
            sleep(5)

            vector = (build_vectors())
            # header_count = 0

            for dictionary in vector:
                for i in dictionary:
                    #uniqueID = dictionary[i].get('uuid')
                    subregion = dictionary[i].get('subregion')
                    #range_ = dictionary[i].get('range')
                    alive = dictionary[i].get('alive')
                    birthday = dictionary[i].get('birthday')
                    lifetime = dictionary[i].get('lifetime')
                    susceptible = dictionary[i].get('susceptible')
                    exposed = dictionary[i].get('exposed')
                    infected = dictionary[i].get('infected')
                    removed = dictionary[i].get('removed')
                    # x = dictionary[i].get('x')
                    #y = dictionary[i].get('y')

                    # if header_count == 0:
                    #    lineOut = ['Vector ID', 'Range', 'Lifetime', 'x', 'y']
                    #    header_count = 1

                    # else:
                    # lineOut = [i, range, lifetime, x, y]
                    # writer(vector_structure_file, lineOut)

                    new_vector = Vectors(
                        # uniqueID=uniqueID,
                        subregion=subregion,
                        #range=range_,
                        alive=alive,
                        birthday=birthday,
                        lifetime=lifetime,
                        susceptible=susceptible,
                        infected=infected,
                        removed=removed
                        # x=x,
                        #y=y
                    )

                    session.add(new_vector)
                session.commit()
            del vector[:]
            input("Vector population table successfully built. Press enter to return to main menu.")
    except KeyboardInterrupt:
        input("You interrupted me! Press enter to return to main menu.")
        main_menu()

def euclidian():
    """
    Calculate distance between points on 2d surface
    :return:
    """


def simulation():  #TODO: This needs to be refactored.
    """
    Simulation class
    :return:
    """

    # TODO: Create backup_table function and use here.
    # TODO: Auto end simulation if infections end
    # TODO: Fix total exposed counter
    # TODO: Break down simulation by subregion, to allow for GIS analysis.


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
    # infected_count = session.query(Humans).filter_by(infected='True').count()
    number_vectors = session.query(Vectors).count()
    total_exposed = 0

    clear_screen()

    if days_to_run >= 365:
        print("Currently running simulation. This will take a while. \nGrab some coffee and catch up on some reading.")
        sleep(3)

    row = session.query(Humans).yield_per(1000)  # This might be way more efficient
    population = dict(
        (r.id, {
            'id': r.id,
            'subregion': r.subregion,
            'importer': r.importer,
            'importDay': r.importDay,
            'pregnant': 'False',
            'susceptible': r.susceptible,
            'infected': r.infected,
            'exposed': r.exposed,
            'recovered': r.recovered,
            'dayOfInf': r.dayOfInf,
            'dayOfExp': r.dayOfExp,
            'biteCount': 0
        }) for r in row
    )

    for p in population:
        subregion = population.get(p)['subregion']

        if subregion not in subregion_list:
            subregion_list.append(subregion)


    vectors = session.query(Vectors).yield_per(1000)  # TODO: Optimize this. Currently VERY slow queries.
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

    try:
        while day < days_to_run and converged == False:  # TODO: Finish this next.
            for subregion in subregion_list:
                biteable_humans = number_humans
                susceptible_count = 0
                exposed_count = 0
                infected_count = 0
                recovered_count = 0
                vector_list = []
                vector_susceptible_count = 0
                vector_infected_count = 0
                vector_removed_count = 0
                i = 0

                for p in population:
                    if population.get(p)['subregion'] == subregion:
                        id_list.append(p)

                for v in vectors:
                    if vectors.get(v)['birthday'] == day and \
                                    vectors.get(v)['alive'] == 'False' and \
                                    vectors.get(v)['removed'] == 'False':  # Number of vectors varies each day
                        vectors.get(v)['alive'] = 'True'
                        vectors.get(v)['susceptible'] = 'True'
                    vector_list.append(v)  # TODO: Find a way to deal with this as it makes the sim slow.

                if day == 0:  # Start log at day 0
                    susceptible_count = session.query(Humans).filter_by(and_(susceptible='True',
                                                                             subregion=subregion)).count()
                    log_entry = Log(Day=day,
                                    nSusceptible=initial_susceptible_humans,
                                    nExposed=exposed_count,
                                    nInfected=infected_count,
                                    nRecovered=recovered_count,
                                    nDeaths='NULL',
                                    nBirthInfections='NULL',
                                    nInfectedVectors=vector_infected_count,
                                    nSuscVectors=initial_susceptible_vectors,
                                    nRemovedVectors=vector_removed_count)
                    session.add(log_entry)
                    session.commit()

                # Run human-human interactions
                for r in id_list:
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

                    while contact_counter < contact_rate:  # Infect by contact rate per day
                        # Choose any random number except the one that identifies the person selected, 'h'
                        pid = random.choice(id_list)
                        while pid == r:
                            pid = random.choice(id_list)
                        person_b = population.get(pid)

                        if person_a['infected'] == 'True':
                            if random.uniform(0, 1) < kappa:  # chance of infection
                                person_b['exposed'] = 'True'
                                person_b['susceptible'] = 'False'
                                total_exposed += 1

                        # the infection can go either way
                        elif person_b['infected'] == 'True':
                            if random.uniform(0, 1) < kappa:  # chance of infection
                                person_a['exposed'] = 'True'
                                person_a['susceptible'] = 'False'

                        contact_counter += 1

                # Run mosquito-human interactions
                for v in vector_list:
                    i = 0
                    if vectors.get(r)['subregion'] == subregion:
                        vector = vectors.get(v)
                        if vector['alive'] == 'True':
                            while i < biting_rate and biteable_humans > 0:

                                pid = random.choice(id_list)  # Pick a human to bite
                                while population.get(pid)['subregion'] != subregion:
                                    pid = random.choice(id_list)
                                person = population.get(pid)

                                if person['susceptible'] == 'True' and vector['infected'] == 'True' and random.uniform(
                                        0, 1) < beta:
                                    person['susceptible'] = 'False'
                                    person['exposed'] = 'True'

                                elif person['infected'] == 'True' and vector['susceptible'] == 'True':
                                    vector['susceptible'] = 'False'
                                    vector['infected'] = 'True'
                                person['biteCount'] += 1

                                if person['biteCount'] >= bite_limit:
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

                clear_screen()
                print("Epidemiological Model Running\n")
                print("Simulating day {0} of {1}".format(day, days_to_run))
                print("\n---------------------------------"
                      "\nSusceptible hosts:    {0}     "
                      "\nExposed hosts:        {1}     "
                      "\nInfected hosts:       {2}     "
                      "\nRecovered hosts:      {3}     "
                      "\n=============================="
                      "\nSusceptible vectors:  {4}     "
                      "\nInfected vectors:     {5}     "
                      "\nRemoved vectors:      {6}     "
                      "\n--------------------------------"
                      .format(susceptible_count, exposed_count, infected_count, recovered_count,
                              vector_susceptible_count, vector_infected_count, vector_removed_count))

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
            day += 1

            #if vector_infected_count == 0 and

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

        input("\nPress enter to return to main menu.")

        # TODO: human within 'range' of mosquito - chance of infection
    except KeyboardInterrupt:
        session.commit()
        clear_screen()
        input("You interrupted me. Going back to main menu.")
        main_menu()


def setupDB():
    """
    Set up the sqlite DB
    :return: a sqlalchemy session
    """

    global working_directory
    global working_directory_set
    global session

    engine = create_engine('sqlite:///simulation.epi')
    DBSession = sessionmaker(bind=engine)
    session = DBSession()

    return session


def read_db():
    """
    Reads existing .epi db
    :return: A sqlalchemy session
    """

    global session

    try:
        dbPath = 'simulation.epi'
        engine = create_engine('sqlite:///%s' % dbPath, echo=False)

        metadata = MetaData(engine)
        population = Table('Humans', metadata, autoload=True)
        vectors = Table('Vectors', metadata, autoload=True)

        # mapper(Humans, population)
        # mapper(Vectors, vectors)

        Session = sessionmaker(bind=engine)
        session = Session()

        clear_screen()
        input("\n\nSuccessfully loaded database. Press enter to return to the main menu.")

        return session
    except:
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
            population = Table('Humans', metadata, autoload=True)
            population.drop(engine)
            setupDB()

        elif table_drop == 'Vectors':
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
        input("Could not droptable. Make sure database is named 'simulatione.epi,' and that it is loaded."
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
                  "6. Main Menu\n".format(simulation_parameters_set,
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
                if config_dict[option] == -1:
                    DebugPrint("skip: {}".format(option))
            except:
                print("Exception on {}".format(option))
                config_dict = None
            return config_dict

        else:
            try:
                config_dict[option] = config.get(section, option)
                if config_dict[option] == -1:
                    DebugPrint("skip: {}".format(option))
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
    mosquito_susceptible_coef = mosquito_init_infectdread_config_section("VECTOR POPULATION PARAMETERS", False)[
        'mosquito_susceptible_coef']
    mosquito_init_infectd = mosquito_init_infectdread_config_section("VECTOR POPULATION PARAMETERS", False)[
        'mosquito_init_infected']
    biting_rate = mosquito_init_infectdread_config_section("VECTOR POPULATION PARAMETERS", False)['biting_rate']
    mosquito_exposed = mosquito_init_infectdread_config_section("VECTOR POPULATION PARAMETERS", False)[
        'mosquito_exposed']
    season_start = mosquito_init_infectdread_config_section("VECTOR POPULATION PARAMETERS", False)['season_start']
    season_end = mosquito_init_infectdread_config_section("VECTOR POPULATION PARAMETERS", False)['season_end']


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
                  "4. Build host data\n"
                  "5. Build vector data\n"
                  "6. Main menu\n")

            answer = input(">>> ")

            if answer.startswith('1'):
                create_config_file()

            if answer.startswith('2'):
                session = read_config_file()

            if answer.startswith('3'):
                read_db()

            if answer.startswith('4'):
                if not working_directory_set:
                    working_directory = input("Path to subregions.csv: ")
                    working_directory_set = True
                setupDB()

                build_population_files(working_directory, 'Humans')

            if answer.startswith('5'):
                if not working_directory_set:
                    working_directory = input("Path to subregions.csv: ")
                    working_directory_set = True
                setupDB()

                build_population_files(working_directory, 'Vectors')

            if answer.startswith('6'):
                main_menu()

        except KeyboardInterrupt:
            main_menu()


def main_menu():
    """
    The main menu of options
    :return:
    """

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
                die()

        except KeyboardInterrupt:
            main_menu()


if __name__ == '__main__':
    main_menu()
