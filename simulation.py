"""
A SEIR simulation that uses SQLite and CSV Census files to define population paramaters
"""

# TODO: Use spatialite db to allow spatial analyses of results and perhaps random walk simulations for vectors
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

# Simulation parameters
days_to_run = 365
random.seed(5)

# Epidemic parameters
causes_death = False
death_chance = .001
beta = .05
gamma = .3  # TODO: See how this interacts with infectious period.
sigma = .35  # TODO: See how this interacts with infectious period.
mu = .1
theta = .1  # mother -> child transmission
birthrate = 0  # birth rate
kappa = .1  # sexual contact
zeta = .1  # blood transfusion
tau = 1  # chance a mosquito picks up zika from human
infectious_period = 5
latent_period = 3

# Human population parameters
initial_susceptible = 750000  # Unused with subregions file
initial_exposed = 0
initial_infected = 3
contact_rate = 5

# Vector population parameters
mosquito_susceptible_coef = 100  # mosquitos per square kilometer
mosquito_exposed = 0
mosquito_init_infectd = 0
biting_rate = 5  # average bites per day


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

            for dictionary in population:  # Human dictionary
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
                    #dayOfRec = dictionary[i].get('dayOfRec')
                    resistant = dictionary[i].get('resistant')
                    x = dictionary[i].get('x')
                    y = dictionary[i].get('y')

                    if sex == "Female":
                        if age >= 14 and age < 51:
                            pregnancy_eligible += 1
                    if pregnant == 'True':
                        pregnant_count += 1

                    new_human = Humans(
                        # uniqueID=uniqueID,
                        subregion=subregion,
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

            # This is bad - it has very high overhead.
            # Create initial human infections
            if initial_infected > 0:  # Only run if we start with human infections
                initial_infection_counter = 0
                row_count = 1
                for i in range(initial_infected):
                    infectList.append(random.randint(1, len(population)))  # Select random person, by id, to infect
                del population[:]  # Delete the population dictionary, because it's massive
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
                    lifetime = dictionary[i].get('lifetime')
                    susceptible = dictionary[i].get('susceptible')
                    exposed = dictionary[i].get('exposed')
                    infected = dictionary[i].get('infected')
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
                        #lifetime=lifetime,
                        susceptible=susceptible,
                        infected=infected,
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



def simulation():
    """
    Simulation class
    :return:
    """

    # TODO: Create backup_table function and use here.
    rowNum = 1
    day = 1

    id_list = []
    vector_list = []
    number_humans = session.query(Humans).count()
    initial_susceptible_humans = session.query(Humans).filter_by(susceptible='True').count()
    susceptible_count = initial_susceptible_humans
    exposed_count = 0
    recovered_count = 0
    nInfectedVectors = 1
    nSuscVectors = 1
    infected_count = session.query(Humans).filter_by(infected='True').count()
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
            'pregnant': 'False',
            'susceptible': r.susceptible,
            'infected': r.infected,
            'exposed': r.exposed,
            'recovered': r.recovered,
            'dayOfInf': r.dayOfInf,
            'dayOfExp': r.dayOfExp,
        }) for r in row
    )

    for p in population:
        id_list.append(p)

    vectors = session.query(Vectors).yield_per(1000)  # TODO: Optimize this. Currently VERY slow queries.
    vectors = dict(
        (v.id, {
            'id': v.id,
            'subregion': v.subregion,
            'susceptible': v.susceptible,
            'infected': v.infected,
        }) for v in vectors
    )

    for v in vectors:
        vector_list.append(v)

    try:
        for d in range(days_to_run):  # TODO: Finish this next.
            clear_screen()
            print("Epidemiological Model Running\n")
            print("Simulating day {0} of {1}".format(d, days_to_run))

            # Run human-human interactions
            for r in id_list:
                person_a = population.get(r)
                i = 0

                if person_a['exposed'] == 'True':
                    if person_a['dayOfExp'] >= latent_period:
                        person_a['exposed'] = 'False'
                        person_a['infected'] = 'True'
                        exposed_count -= 1
                        infected_count += 1

                    else:
                        person_a['dayOfExp'] += 1

                while i < contact_rate:  # Infect by contact rate per day
                    # Choose any random number except the one that identifies the person selected, 'h'
                    pid = random.choice(id_list)
                    while pid == r:
                        pid = random.choice(id_list)

                    # make sure to make infections go both ways here!!
                    if random.uniform(0, 1) < beta:  # chance of infection
                        person_b = population.get(pid)

                        person_b['exposed'] = 'True'
                        person_b['susceptible'] = 'False'
                        total_exposed += 1
                        susceptible_count += - 1
                        exposed_count += 1
                        person_b['dayOfInf'] += 1
                    i += 1

                if person_a['dayOfInf'] >= infectious_period:
                    if causes_death:
                        person_a['infected'] = 'False'
                        if random.uniform(0, 1) < death_chance:
                            person_a['dead'] = 'True'
                            infected_count -= 1
                        else:
                            person_a['recovered'] = 'True'
                            infected_count -= 1
                            recovered_count += 1
                    else:
                        person_a['infected'] = 'False'
                        person_a['recovered'] = 'True'
                        infected_count -= 1
                        recovered_count += 1

                    person_a['dayOfInf'] += 1

            # Run mosquito-human interactions

            for v in vector_list:
                i = 0
                vector = vectors.get(v)

                while i < biting_rate:
                    pid = random.choice(id_list)  # Pick a human to bite
                    person = population.get(pid)

                    if person['susceptible'] == 'True' and vector['infected'] == 'True' and random.uniform(0, 1) < beta:
                        person['susceptible'] = 'False'
                        person['exposed'] = 'True'
                        exposed_count += 1
                        total_exposed += 1
                        susceptible_count -= 1

                    elif person['infected'] == 'True' and vector['susceptible'] == 'True':
                        vector['susceptible'] = 'False'
                        vector['infected'] = 'True'
                        nInfectedVectors += 1
                        nSuscVectors -= 1
                    i += 1

            log_entry = Log(Day=d + 1,
                            nSusceptible=susceptible_count,
                            nExposed=exposed_count,
                            nInfected=infected_count,
                            nRecovered=recovered_count,
                            nDeaths='NULL',
                            nBirthInfections='NULL')
            session.add(log_entry)
            day += 1
        session.commit()

        clear_screen()
        print("**Post-epidemic Report**\n\n"
              "- Total Days Run: {0}\n"
              "- Total Exposed: {1}\n"
              "- Average Exposed/Day: {2}\n"
              "- Population Not Exposed: {3}\n".format(days_to_run,
                                                       total_exposed,
                                                       round((total_exposed / days_to_run), 2),
                                                       initial_susceptible_humans - total_exposed))

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
    global session

    working_directory = input("Path to subregions.csv: ")

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
                  "5. Main Menu\n".format(simulation_parameters_set,
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
                    'DaysToRun': input("\nDays to run simulation: "),
                    'Seasonality': prompt("Seasonality in vector poulation?: ")
                }

                with open('simulation.cfg', 'a') as configfile:
                    config.write(configfile)

                simulation_parameters_set = 'Set'

            if answer.startswith('2'):
                clear_screen()
                print("***Python Epidemiological Model***\n"
                      "Host Population Parameters\n")

                config["HOST POPULATION PARAMETERS"] = {
                    'initial_exposed': input("Number of hosts to expose before model begins: "),
                    'initial_infected': input("\nNumber of hosts to infect before model begins: "),
                    'contact_rate': input("\nNumber of contacts per day, per host: ")
                }

                with open('simulation.cfg', 'a') as configfile:
                    config.write(configfile)

                host_population_settings_set = 'Set'

            if answer.startswith('3'):
                clear_screen()
                print("***Python Epidemiological Model***\n"
                      "Vector Population Parameters\n")

                config['VECTOR POPULATION PARAMETERS'] = {
                    'mosquito_susceptible_coef': input("Mosquitos per square kilometer: "),
                    'mosquito_exposed': input("\nNumber of vectors to expose before model begins: "),
                    'mosquito_init_infected': input("\nNumber of vectors to infect before model begins: "),
                    'biting_rate': input("\nNumber of humans each mosquito bites per day: ")
                }

                with open('simulation.cfg', 'a') as configfile:
                    config.write(configfile)

                vector_population_settings_set = 'Set'

            if answer.startswith('4'):
                clear_screen()
                print("***Python Epidemiological Model***\n"
                      "Epidemic Parameters\n")

                config['EPIDEMIC PARAMETERS'] = {
                    'causes_death': prompt("Can disease end in death?"),
                    'death_chance': input("\nIf disease can cause death, what is the probability (0-1)?: "),
                    'beta': input("\nWhat is the beta value (probability of infection)?: "),
                    'gamma': input("\nWhat is the gamma value (Rate at which infected moves to recovery)?: "),
                    'sigma': input("\nWhat is the sigma value (Rate at which an exposed person becomes infective)?: "),
                    'mu': input("\nWhat is the mu value (Natural mortality rate)?: "),
                    'theta': input("\nWhat is the theta value (perinatal transmission rate)?: "),
                    'kappa': input("\nWhat is the kappa value (sexual contact transmission rate)?: "),
                    'infectious_period': input("\nHow long is the disease infectious period, in days?: "),
                    'latent_period': input("\nHow long is the disease latent period, in days?: ")
                }

                with open('simulation.cfg', 'a') as configfile:
                    config.write(configfile)

                disease_parameters_set = 'Set'

            if answer.startswith('5'):
                main_menu()

        except KeyboardInterrupt:
            main_menu()



def main_menu():
    """
    The main menu of options
    :return:
    """

    config = configparser.ConfigParser()

    while True:
        try:
            """Main menu for program. Prompts user for function."""
            clear_screen()
            print("Python Epidemiological Model\n\n"
                  "What would you like to do?\n"
                  "1. Build Population Data\n"
                  "2. Build Vector Data\n"
                  "3. Load Existing Tables\n"
                  "4. Drop Human Tables\n"
                  "5. Drop Vector Tables\n"
                  "6. Run Simulation\n"
                  "7. Quit\n"
                  "8. Model Settings\n")

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
                drop_table('Humans')

            if answer.startswith('5'):
                drop_table('Vectors')

            if answer.startswith('6'):
                simulation()
                # try:
                #    simulation()
                # except NameError:
                #    clear_screen()
                #    input("Database not loaded. Press enter to return to the main menu.")
                #    main_menu()

            if answer.startswith('7'):
                die()

            if answer.startswith('8'):
                create_config_file()

        except KeyboardInterrupt:
            main_menu()


if __name__ == '__main__':
    main_menu()
