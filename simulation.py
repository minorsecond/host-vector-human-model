import csv
import os.path
import random
from sys import exit as die
from time import sleep

import numpy as np

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
mosquito_susceptible = 1000000
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


def build_population(N):
    """
    Builds population with parameters
    :param N: Population size
    :return: Dict of dicts N size, with parameters
    """
    # Dict of dicts, with each key having its own parameters
    population = dict(
        (i, {
            'age': random.randint(0,99),
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
            'resistant': False,
            'x': np.random.uniform(689141.000, 737293.000),  # Extents for Tarrant county, TX
            'y': np.random.uniform(2098719.000, 2147597.000)

        }) for i in range(N)
    )

    for x in population:
        if population[x].get('sex') == "Female":
            if population[x].get('age') >= 15 and population[x].get('age') < 51:
                if random.randint(0, 100) < 4:
                    population[x]['pregnant'] = 'True'

    return population


def build_vectors(N):
    """
    Builds vector population
    :param N: Number of vectors
    :return: Dict of dicts N size, with parameters
    """
    infected_mosquitos = 0

    vector_population = dict(
        (i, {
            'range': random.uniform(0, 500),  # 500 meters or so
            'lifetime': random.uniform(0, 14),  # in days
            'susceptible': 'True',
            'exposed': 'False',
            'infected': 'False',
            'x': np.random.uniform(689141.000, 737293.000),  # Extents for Tarrant county, TX
            'y': np.random.uniform(2098719.000, 2147597.000)
        }) for i in range(N)
    )

    # Infect the number of mosquitos set at beginning of script
    for x in vector_population:
        if random.randint(0, N) == x:
            vector_population[x]['infected'] = True

    return vector_population


def writer(filename, line):
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
    population = (build_population(initial_susceptible))
    for i in population:
        age = population[i].get('age')
        sex = population[i].get('sex')
        pregnant = population[i].get('pregnant')
        x = population[i].get('x')
        y = population[i].get('y')

        if sex == "Female":
            if age >= 14 and age < 51:
                pregnancy_eligible += 1
        if pregnant == 'True':
            pregnant_count += 1

        if header_count == 0:
            lineOut = ['Individual ID', 'Age', 'Sex', 'Pregnancy Status', 'x', 'y']
            header_count = 1

        else:
            lineOut = [i, age, sex, pregnant, x, y]
        writer(population_structure_file, lineOut)

        if run_count == 0:
            print('Building population file: {0}% Complete'.format(round(output_status(run_count, len(population)))))

        run_count += 1
        if run_count % (len(population) / 100) == 0:
            print('Building population file: {0}% Complete'.format(round(output_status(run_count, len(population)))))

    # Print vector structure info

    print("Building vector population")
    sleep(5)

    vector = (build_vectors(mosquito_susceptible))
    run_count = 0
    header_count = 0

    for i in vector:
        range = vector[i].get('range')
        lifetime = vector[i].get('lifetime')
        x = vector[i].get('x')
        y = vector[i].get('y')

        if header_count == 0:
            lineOut = ['Vector ID', 'Range', 'Lifetime', 'x', 'y']
            header_count = 1

        else:
            lineOut = [i, range, lifetime, x, y]
        writer(vector_structure_file, lineOut)

        if run_count == 0:
            print('Building vector file: {0}% Complete'.format(round(output_status(run_count, len(population)))))

        run_count += 1
        if run_count % (len(vector) / 100) == 0:
            print('Building vector file: {0}% Complete'.format(round(output_status(run_count, len(vector)))))

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
    working_directory = input("Which directory should I place output data?: ")

    if not os.path.exists(working_directory):
        os.makedirs(working_directory)

    build_population_files(working_directory)


if __name__ == '__main__':
    main()