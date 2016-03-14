

import random

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
mosquito_susceptible = initial_susceptible * 10
mosquito_exposed = 0
mosquito_init_infectd = 0


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

        }) for i in range(N)
    )

    for x in population:
        if population[x].get('sex') == "Female":
            if population[x].get('age') >= 15:
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
            'range': random.normalvariate(0, 500),  # 500 meters or so
            'lifetime': random.uniform(0, 14),  # in days
            'susceptible': 'True',
            'exposed': 'False',
            'infected': 'False',
        }) for i in range(N)
    )

    # Infect the number of mosquitos set at beginning of script
    for x in vector_population:
        if random.randint(0, N) == x:
            vector_population[x]['infected'] = True

    return vector_population


def main():
    pregnancy_eligible = 0
    pregnant_count = 0

    population = (build_population(initial_susceptible))
    for i in population:
        age = population[i].get('age')
        sex = population[i].get('sex')
        pregnant = population[i].get('pregnant')

        if sex == "Female":
            if age >= 14:
                pregnancy_eligible += 1
        if pregnant == 'True':
            pregnant_count += 1

        print("Age: {0} Sex: {1} Pregnancy: {2}".format(age, sex, pregnant))

    if pregnant_count > 0:
        pregnant_percentage = (pregnant_count / pregnancy_eligible) * 100
    else:
        pregnant_percentage = "No pregnancies"
    print("Percent of eligible women pregnant: {0}".format(pregnant_percentage))


def simulation():
    """

    :return:
    """

    day_of_infection = 0


def csv_writer():
    """
    Writes out model values: Median age of population, number of pregnant, etc..
    :return:
    """


if __name__ == '__main__':
    main()