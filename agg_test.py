#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Sep  3 18:45:30 2023

@author: marlon
"""

import Configuration as c
import prepare_data as prepare
import aggregator as a1

import multiprocessing as mp

#import pathos
#mp = pathos.helpers.mp #Solves the pickle problem with Pyomo objects but is so slow its unusable.
from pyomo.environ import *
import logging as log
import pandas as pd
import time
from itertools import repeat
import numpy as np
from matplotlib import pyplot as plt
logger = log.getLogger()
logger.setLevel(log.INFO)

point1 = time.time()


# processes = [mp.Process(target=prepare.initiate_aggregator, args=(a,)) for a in c.aggregators]
# for process in processes:
#    process.start()
# for process in processes:
#    process.join()
#


# seed guarantees randoms differentiate between workers.
init_agg_pool = mp.Pool(processes=2, initializer=np.random.seed())

result = init_agg_pool.map(prepare.initiate_aggregator, c.aggregators)
# for a in c.aggregators:
#        prepare.initiate_aggregator(a)
c.aggregators = result

del init_agg_pool

agg = 0
agg2 = 1
t_start = c.t_start

point2 = time.time()
log.info(f'Took {point2-point1} seconds to initialise aggregators & nodes.')
#manager = mp.Manager()
# model_pool = mp.Pool(processes=len(c.aggregators), initializer=np.random.seed())
models = list()
for aggregator in c.aggregators:
    models += [a1.Aggregator_Model(aggregator, t_start)]


point3 = time.time()
log.info(f'Took {point3-point2} seconds to build an the Aggregator models.')

# parasolve1 = time.time()

# processes = []
# for model in models:
#     solver = c.AggregatorSolver()
#     processes += [mp.Process(target=solver.solve, args=(model,))]
# for process in processes:
#     process.start()

# for process in processes:
#     process.join()

# parasolve2 = time.time()
# print(f'Parallel solve took {parasolve2-parasolve1} seconds.')



for model in models:

    solver = SolverFactory('cplex', executable=c.cplex_path)

    # model.write('test2.lp',format='cpxlp')
    if c.set_memory_emphasis:
        solver.options['set emphasis memory 1']

    memstring = 'set workmem '+str(c.RAM)
    solver.options[memstring]
    # solver.options['set threads 6'] #no gain seen
    results = solver.solve(model)


# solver2.options['set workmem 24000']
# solver2.options['set threads 6']
# results = solver2.solve(model2)
# results = solver.solve(model,tee=True)

point4 = time.time()
log.info(f'Took {point4-point3} seconds to solve the models.')

for model in models:

    for p_solar_index in list(model.P_solar.index_set()):
        model.P_solar[p_solar_index].fix()
        model.P_batt[p_solar_index].fix()
point4 = time.time()


for model in models:

    solver = c.AggregatorSolver()

    # model.write('test2.lp',format='cpxlp')
    # solver.options['set threads 6'] #no gain seen
    results = solver.solve(model, warmstart=True)


pointx = time.time()
log.info(f'Took {pointx-point4} seconds to warm-solve the models.')

variables = dict()
for v in model.component_objects(Var, active=True):
    variables[name(v)] = [(index, value(v[index])) for index in v]

var_names = list(variables.keys())
nodes = c.aggregators[agg]['Nodes'].keys()
T = list(range(int(t_start), t_start+int(c.horizon_intervals)))

data = dict()
for n in nodes:
    data[n] = dict()
    for t in T:
        data[n][t] = dict()

for metric in var_names[:5]:
    for item in variables[metric]:
        n = item[0][0]
        t = item[0][1]
        v = item[1]
        data[n][t][metric] = v


for n in nodes:
    old_df = c.aggregators[agg]['Nodes'][n]
    new_df = pd.DataFrame(data[n]).transpose()
    metrics = var_names[:5]
    for metric in metrics:
        old_df[metric][t_start:int(
            c.horizon_intervals+t_start)] = new_df[metric]


c.aggregators[agg]['Nodes'][0].to_csv('node_fill.csv')
nodetest = pd.DataFrame(data[3]).transpose()
nodetest.to_csv('node_output.csv')

df = c.aggregators[agg]['Nodes'][0][int(
    t_start):int(t_start+c.horizon_intervals)]


def plot_node(n):
    df = c.aggregators[agg]['Nodes'][n][int(
        t_start):int(t_start+c.horizon_intervals)]
    plt.plot(df['P_solar'], color='orange', label='P_Solar')
    plt.plot(df['P_meter'], color='blue', label='P_Meter')
    plt.plot(df['P_batt'], color='red', label='P_Battery')
    plt.plot(df['P_load'], color='green', label='P_Load')
    plt.plot(df['SOC'], color='pink', label='SOC')
    plt.plot(df['SOC_min'], color='black', label='$/kWh Import')
    plt.show()
    # plt.plot(df['R_bid'],color='maroon',label='$/kWhfor b in buses.index: Export')
    # plt.legend()


online_total_fraction = sum(
    [x[1] for x in variables['Online']])/len(variables['Online'])
assert c.nu*0.98 <= 1-round(online_total_fraction,
                            1) <= c.nu*1.02, 'Offline targetting went wrong.'

point5 = time.time()
log.info(f'Took {point5-point4} seconds to process data.')
log.info(f'Overall, it took {point5-point1} seconds to run.')
log.info('Script finished.')
