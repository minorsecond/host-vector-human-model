"""
A SEIR simulation that uses SQLite and CSV Census files to define population paramaters
"""

import csv
import os.path
import random
from sys import exit as die
from time import sleep
from uuid import uuid4 as uuid

import numpy as np
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db import Humans, Vectors

# Simulation parameters
days_to_run = 999
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
initial_infected = 1

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
    :param N: Population size
    :return: Dict of dicts N size, with parameters
    """

    subregions_list = []

    in_subregion_data = os.path.join(working_directory, 'subregions.csv')
    sub_regions_dict = sub_regions(in_subregion_data)

    print('Building population for {0} sub-regions. This whill take a second..'.format(len(sub_regions_dict) - 1))

    for i in sub_regions_dict:
        subregion = i
        pop = sub_regions_dict[i].get('pop')

        population = dict(
            (x, {
                'uuid': uuid(),
                'subregion': subregion,
                'age': random.randint(0, 99),
                'sex': random.choice(['Male', 'Female']),
                'pregnant': 'False',
                'susceptible': 'True',
                'infected': 'False',
                'exposed': 'True',
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
    :param N: Number of vectors
    :return: Dict of dicts N size, with parameters
    """
    infected_mosquitos = 0
    subregions_list = []

    in_subregion_data = os.path.join(working_directory, 'subregions.csv')
    sub_regions_dict = sub_regions(in_subregion_data)

    print('Building vector population for {0} sub-regions. This will take a second..'.format(len(sub_regions_dict)))

    for i in sub_regions_dict:
        subregion = i
        area = float(sub_regions_dict[i].get('area'))
        vector_pop = int((area / 1000000) * mosquito_susceptible_coef)  # sq. meters to square km

        vector_population = dict(
            (x, {
                'uuid': uuid(),
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
                vector_population[x]['infected'] = True

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

    return ((n / total) * 100)


def build_population_files(directory):
    population_structure_file = os.path.join(directory, 'human_population.csv')
    check_if_file_exists(population_structure_file)

    vector_structure_file = os.path.join(directory, 'vector_population.csv')
    check_if_file_exists(vector_structure_file)

    pregnancy_eligible = 0
    pregnant_count = 0
    header_count = 0
    run_count = 0

    # Print population structure info
    population = (build_population())

    # while header_count == 0:
    #    lineOut = ['Subregion ID:, Individual ID', 'Age', 'Sex', 'Pregnancy Status']
    #    header_count = 1
    #    writer(population_structure_file, lineOut)

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

                # else:
                #    lineOut = [subregion, i, age, sex, pregnant]
                #writer(population_structure_file, lineOut)

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

            if run_count == 0:
                print('\nBuilding population file: {0}% Complete'.format(
                    round(output_status(run_count, len(dictionary)))))

            run_count += 1
            if run_count % (len(dictionary) / 100) == 0:
                print('Building population file: {0}% Complete'.format(round(output_status(run_count, len(dictionary)))))
    session.commit()

    # Print vector structure info

    print("Building vector population")
    sleep(5)

    vector = (build_vectors())
    run_count = 0
    #header_count = 0

    for dictionary in vector:
        for i in dictionary:
            uniqueID = uniqueID,
            subregion = dictionary[i].get('subregion')
            range = dictionary[i].get('range')
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
            #writer(vector_structure_file, lineOut)

            new_vector = Vectors(
                uniqueID=uniqueID,
                subregion=subregion,
                range=range,
                lifetime=lifetime,
                susceptible=susceptible,
                exposed=exposed,
                infected=infected,
                x=x,
                y=y
            )

            session.add(new_vector)

            if run_count == 0:
                print('Building vector file: {0}% Complete'.format(round(output_status(run_count, len(population)))))

            run_count += 1
            if run_count % (len(vector) / 100) == 0:
                print('Building vector file: {0}% Complete'.format(round(output_status(run_count, len(vector)))))
    session.commit()

    # stats

    if pregnant_count > 0:
        pregnant_percentage = (pregnant_count / pregnancy_eligible) * 100
    else:
        pregnant_percentage = "\nNo pregnancies"
    print("\nPercent of eligible women pregnant: {0}".format(pregnant_percentage))


def simulation():
    """

    :return:
    """

    day_of_infection = 0


def main():
    global working_directory
    global session

    working_directory = input("Which directory should I place output data?: ")

    if not os.path.exists(working_directory):
        os.makedirs(working_directory)

    db_name = 'Simulation.db'
    db_path = os.path.join(working_directory, db_name)

    engine = create_engine('sqlite:///simulation.db')
    DBSession = sessionmaker(bind=engine)
    session = DBSession()

    build_population_files(working_directory)


if __name__ == '__main__':
    main()