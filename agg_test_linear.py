# -*- coding: utf-8 -*-

"""
Created on Sun Sep  3 18:45:30 2023

@author: marlon
"""

import Configuration as c
import prepare_data as prepare
import aggregator1 as a1
import multiprocessing as mp

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


#processes = [mp.Process(target=prepare.initiate_aggregator, args=(a,)) for a in c.aggregators]
#for process in processes:
#    process.start()
#for process in processes:
#    process.join()
#    

init_agg_pool = mp.Pool(processes=2, initializer=np.random.seed()) #seed guarantees randoms differentiate between workers.

result = init_agg_pool.map(prepare.initiate_aggregator,c.aggregators)
#for a in c.aggregators:
#        prepare.initiate_aggregator(a)
c.aggregators = result

del init_agg_pool

agg = 0
agg2 = 1
t_start = 1

point2 = time.time()
log.info(f'Took {point2-point1} seconds to initialise aggregators & nodes.')




    
model  = a1.Aggregator_Optimisation(c.aggregators[agg],t_start)
model2 = a1.Aggregator_Optimisation(c.aggregators[agg2],t_start)

point3 = time.time()
log.info(f'Took {point3-point2} seconds to build an the Aggregator {agg} model.')

solver = SolverFactory('cplex',executable = '/opt/ibm/ILOG/CPLEX_Studio2211/cplex/bin/x86-64_linux/cplex')
solver.options['set workmem 24000']

solver2 = SolverFactory('cplex',executable = '/opt/ibm/ILOG/CPLEX_Studio2211/cplex/bin/x86-64_linux/cplex')
solver2.options['set workmem 24000']


results = solver.solve(model)
results2 = solver2.solve(model2)
    

#solver2.options['set workmem 24000']
#solver2.options['set threads 6']
#results = solver2.solve(model2)
#results = solver.solve(model,tee=True) 

point4 = time.time()
log.info(f'Took {point4-point3} seconds to solve the model.')

variables = dict()
for v in model.component_objects(Var, active = True):
    variables[name(v)] = [(index,value(v[index])) for index in v]

var_names = list(variables.keys())
nodes = c.aggregators[agg]['Nodes'].keys()
T = list(range(int(t_start),t_start+int(c.horizon_intervals)))

#variables = {var_name: [(n,t),value]}
data = dict()
data['Aggregate'] = dict()
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
        old_df[metric][t_start:int(c.horizon_intervals+t_start)] = new_df[metric] 
    

    
c.aggregators[agg]['Nodes'][0].to_csv('node_fill.csv')
nodetest = pd.DataFrame(data[3]).transpose()
nodetest.to_csv('node_output.csv')
        
df = c.aggregators[agg]['Nodes'][0][int(t_start):int(t_start+c.horizon_intervals)]

def plot_node(n):
    df = c.aggregators[agg]['Nodes'][n][int(t_start):int(t_start+c.horizon_intervals)]
    plt.plot(df['P_solar'], color ='orange',label='P_Solar')
    plt.plot(df['P_meter'], color = 'blue',label='P_Meter')
    plt.plot(df['P_batt'], color = 'red',label='P_Battery')
    plt.plot(df['P_load'], color = 'green',label = 'P_Load')
    plt.plot(df['SOC'], color = 'pink',label='SOC')
    plt.plot(df['SOC_min'],color='black',label='$/kWh Import')
    plt.show()
    #plt.plot(df['R_bid'],color='maroon',label='$/kWh Export')
    #plt.legend()



online_total_fraction = sum([x[1] for x in variables['Online']])/len(variables['Online'])
assert c.nu*0.98 <= 1-round(online_total_fraction,1) <= c.nu*1.02, 'Offline targetting went wrong.'

point5 = time.time()
log.info(f'Took {point5-point4} seconds to process data.')
log.info(f'Overall, it took {point5-point1} seconds to run.')
log.info('Script finished.')