

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
initial_susceptible = 9999999
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
            'sex': random.randint(0,1),
            'pregnant': 'False',
            'susceptible': 'True',
            'infected': 'False',
            'exposed': 'True',
            'recovered': 'False',
        }) for i in range(N)
    )

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
    population = (build_population(999))
    for i in population:
        age = population[i].get('age')
        _sex = population[i].get('sex')

        if _sex == 0:
            sex = 'male'
        else:
            sex = 'female'

        print("Age: {0} Sex: {1}".format(age, sex))

if __name__ == '__main__':
    main()