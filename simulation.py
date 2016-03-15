"""
A SEIR simulation that uses SQLite and CSV Census files to define population paramaters
"""

# TODO: Add option to load previously-created tables into tool.
# TODO: Use spatialite db to allow spatial analyses of results and perhaps random walk simulations for vectors

import csv
import os.path
import random
from sys import exit as die
from time import sleep
from uuid import uuid4 as uuid

import numpy as np
from sqlalchemy import create_engine, MetaData, Table
from sqlalchemy.orm import sessionmaker

from db import Humans, Vectors

# Simulation parameters
days_to_run = 5
random.seed(5)

# Epidemic parameters
beta = .25
gamma = .3
sigma = .35
mu = .1
theta = .1  # mother -> child transmission
kappa = .1  # sexual contact
zeta = .1  # blood transfusion
tau = .1  # chance a mosquito picks up zika from human

# Human population parameters
initial_susceptible = 750000
initial_exposed = 0
initial_infected = 9
contact_rate = 5

# Mosquito population parameters
mosquito_susceptible_coef = 200  # mosquitos per square kilometer
mosquito_exposed = 0
mosquito_init_infectd = 0


def prompt(question):
    reply = str(input(question + ' (y/n): ')).lower().strip()
    if reply[0] == 'y':
        return True
    if reply[0] == 'n':
        return False
    else:
        return question("Try again: ")


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
        subregion = i
        pop = sub_regions_dict[i].get('pop')

        population = dict(
            (x, {
                'uuid': str(uuid()),
                'subregion': subregion,
                'age': random.randint(0, 99),
                'sex': random.choice(['Male', 'Female']),
                'pregnant': 'False',
                'susceptible': 'True',
                'infected': 'False',
                'exposed': 'False',
                'recovered': 'False',
                'dayOfInf': 0,
                'dayOfExp': 0,
                'dayOfRec': 0,
                'recState': 0,
                'resistant': 'False',
                'x': np.random.uniform(689141.000, 737293.000),  # Extents for Tarrant county, TX
                'y': np.random.uniform(2098719.000, 2147597.000)

            }) for x in range(pop)
        )

        for x in population:
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

    in_subregion_data = os.path.join(working_directory, 'subregions.csv')
    sub_regions_dict = sub_regions(in_subregion_data)

    clear_screen()
    print('Building vector population for {0} sub-regions. This will take a second..'.format(len(sub_regions_dict)))

    for i in sub_regions_dict:
        subregion = i
        area = float(sub_regions_dict[i].get('area'))
        vector_pop = int((area / 1000000) * mosquito_susceptible_coef)  # sq. meters to square km

        vector_population = dict(
            (x, {
                'uuid': str(uuid()),
                'subregion': subregion,
                'range': random.uniform(0, 500),  # 500 meters or so
                'lifetime': random.uniform(0, 14),  # in days
                'susceptible': 'True',
                'exposed': 'False',
                'infected': 'False',
                'x': np.random.uniform(689141.000, 737293.000),  # Extents for Tarrant county, TX
                'y': np.random.uniform(2098719.000, 2147597.000)
            }) for x in range(vector_pop)
        )

    # Infect the number of mosquitos set at beginning of script
        for x in vector_population:
            if np.random.uniform(0, 1) < .01:
                vector_population[x]['infected'] = 'True'
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
        has_header = csv.Sniffer().has_header(csvfile.read(1024))
        csvfile.seek(0)
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


def build_population_files(directory, tableToBuild):
    global session

    # while header_count == 0:
    #    lineOut = ['Subregion ID:, Individual ID', 'Age', 'Sex', 'Pregnancy Status']
    #    header_count = 1
    #    writer(population_structure_file, lineOut)

    idList = []
    infectList = []

    try:

        if tableToBuild == 'Humans':

            population_structure_file = os.path.join(directory, 'human_population.csv')
            check_if_file_exists(population_structure_file)

            # Print population structure info
            population = (build_population())

            pregnancy_eligible = 0
            pregnant_count = 0

            for dictionary in population:
                for i in dictionary:
                    uniqueID = dictionary[i].get('uuid')
                    subregion = dictionary[i].get('subregion')
                    age = dictionary[i].get('age')
                    sex = dictionary[i].get('sex')
                    pregnant = dictionary[i].get('pregnant')
                    susceptible = dictionary[i].get('susceptible')
                    exposed = dictionary[i].get('exposed')
                    infected = dictionary[i].get('infected')
                    recovered = dictionary[i].get('recovered')
                    dayOfInf = dictionary[i].get('dayOfInf')
                    dayOfExp = dictionary[i].get('dayOfExp')
                    dayOfRec = dictionary[i].get('dayOfRec')
                    resistant = dictionary[i].get('resistant')
                    x = dictionary[i].get('x')
                    y = dictionary[i].get('y')

                    if sex == "Female":
                        if age >= 14 and age < 51:
                            pregnancy_eligible += 1
                    if pregnant == 'True':
                        pregnant_count += 1

                    new_human = Humans(
                        uniqueID=uniqueID,
                        subregion=subregion,
                        age=age,
                        sex=sex,
                        pregnant=pregnant,
                        susceptible=susceptible,
                        exposed=exposed,
                        infected=infected,
                        recovered=recovered,
                        dayOfInf=dayOfInf,
                        dayOfExp=dayOfExp,
                        dayOfRec=dayOfRec,
                        resistant=resistant,
                        x=x,
                        y=y
                    )

                    session.add(new_human)
                session.commit()

            # This is bad - it has very high overhead.
            if initial_infected > 0:  # Create the initial infections
                initial_infection_counter = 0
                row_count = 1
                for i in range(initial_infected):
                    infectList.append(random.randint(1, len(population)))
                del population[:]
                clear_screen()
                print("- Infecting {0} individuals to start the simulation.".format(initial_infected))
                for i in infectList:
                    while initial_infection_counter < initial_infected:
                        for h in infectList:  # For each ID in the infected list,
                            row = session.query(Humans).filter_by(
                                id=h)  # select a human from the table whose ID matches
                            for r in row:
                                print("Scanned row {0} of {1}".format(row_count, session.query(Humans).count()))
                                if r.id in infectList:  # This might be redundant.
                                    row.update({"susceptible": 'False'}, synchronize_session='fetch')
                                    row.update({"exposed": 'False'}, synchronize_session='fetch')
                                    row.update({"infected": 'True'}, synchronize_session='fetch')
                                    row.update({"recovered": 'False'}, synchronize_session='fetch')
                                    initial_infection_counter += 1
                                row_count += 1

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
                    uniqueID = dictionary[i].get('uuid')
                    subregion = dictionary[i].get('subregion')
                    range_ = dictionary[i].get('range')
                    lifetime = dictionary[i].get('lifetime')
                    susceptible = dictionary[i].get('susceptible')
                    exposed = dictionary[i].get('exposed')
                    infected = dictionary[i].get('infected')
                    x = dictionary[i].get('x')
                    y = dictionary[i].get('y')

                    # if header_count == 0:
                    #    lineOut = ['Vector ID', 'Range', 'Lifetime', 'x', 'y']
                    #    header_count = 1

                    # else:
                    # lineOut = [i, range, lifetime, x, y]
                    # writer(vector_structure_file, lineOut)

                    new_vector = Vectors(
                        uniqueID=uniqueID,
                        subregion=subregion,
                        range=range_,
                        lifetime=lifetime,
                        susceptible=susceptible,
                        exposed=exposed,
                        infected=infected,
                        x=x,
                        y=y
                    )

                    session.add(new_vector)
            session.commit()
            del vector[:]
    except KeyboardInterrupt:
        input("You interrupted me! Press enter to return to main menu.")
        main_menu()

def euclidian():
    """
    Calculate distance between points on 2d surface
    :return:
    """



def simulation():
    """
    Simulation class
    :return:
    """
    rowNum = 1
    day = 1
    syms = ['\\', '|', '/', '-']
    bs = '\b'

    number_humans = session.query(Humans).count()
    number_vectors = session.query(Vectors).count()

    clear_screen()

    print("Currently running simulation. This will take a while. \nGrab some coffee and catch up on some reading.")

    try:
        for d in range(days_to_run):  # TODO: Finish this next.
            for h in range(number_humans):
                row = session.query(Humans).filter_by(id=h)  # TODO:  handle situations where h doesn't match any ID
                for r in row:
                    i = 0
                    while i < contact_rate - 1:  # Infect by contact rate per ady
                        contact = session.query(Humans).filter_by(id=random.randint(1, number_humans)).first()
                        if contact.exposed == 'True':
                            input('Boom! exposed, fool.')
                            row.update({"exposed": 'True'}, synchronize_session='fetch')
                        i += 1
                    rowNum += 1
            day += 1
        session.commit()

        # for human_a in session.query(Humans).yield_per(1000):
        #    i = 0
        #    while i < contact_rate:
        #        for human_b in session.query(Humans).yield_per(1000):
        #            if human_a.id != human_b.id:
        #                #print("Processing row #{0} of {1}".format(rowNum, number_humans * contact_rate * days_to_run))
        #                if human_b.exposed == 'True':
        #                    input("BREAK - THE INFECTION CODE WORKED")
        #                    human_a.update({"exposed": 'True'}, synchronize_session='fetch')
        #                rowNum += 1
        #        i += 1


        # TODO: human within 'range' of mosquito - chance of infection
    except KeyboardInterrupt:
        clear_screen()
        input("You interrupted me. Going back to main menu.")
        main_menu()


def setupDB():
    global working_directory
    global session

    working_directory = input("Path to subregions.csv: ")

    engine = create_engine('sqlite:///simulation.epi')
    DBSession = sessionmaker(bind=engine)
    session = DBSession()

    return session


def read_db():
    """
    Reads existing .epi db
    :return:
    """

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


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def main_menu():
    global working_directory
    global session

    while True:
        try:
            """Main menu for program. Prompts user for function."""
            clear_screen()
            print("Python Epidemiological Model\n\n"
                  "What would you like to do?\n"
                  "1. Build Population Data\n"
                  "2. Build Vector Data\n"
                  "3. Load Existing Tables\n"
                  "4. Run Simulation\n"
                  "5. Quit\n")

            answer = input(">>> ")

            if answer.startswith('1'):
                setupDB()
                build_population_files(working_directory, 'Humans')

            if answer.startswith('2'):
                setupDB()
                build_population_files(working_directory, 'Vectors')

            if answer.startswith('3'):
                session = read_db()

            if answer.startswith('4'):
                try:
                    simulation()
                except NameError:
                    clear_screen()
                    input("Database not loaded. Press enter to return to the main menu.")
                    main_menu()
            if answer.startswith('5'):
                die()

        except KeyboardInterrupt:
            main_menu()


if __name__ == '__main__':
    main_menu()
