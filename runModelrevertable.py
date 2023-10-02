#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Aug 27 00:02:53 2023

@author: marlon
"""
import Configuration as c
import prepare_data as prepare
import aggregator as agg
import dso 
import time
from pyomo.environ import *
import logging as log
logger = log.getLogger()
logger.setLevel(log.INFO)
#Setup

#T = list(range(c.t_start,c.t_end))
T = list(range(1,288))

if not c.feeder['is_built']:
     prepare.initiate_loads()
     prepare.initiate_aggregators()
     c.feeder = prepare.initiate_feeder(c.aggregators)


#log.info(f'Successfully initiated {len(c.aggregators)} aggregators.')

#Top level process:
loop = 1
agg_solver = c.AggregatorSolver()
dso_solver = c.DSOSolver()
for t in T:
    tloop_start = time.time()
    tp1 = time.time()
    aggregator_models = [agg.Aggregator_Model(aggregator, t, mode='prediction', IOEs='inactive') for aggregator in c.aggregators]
    tp2 = time.time()
    a = 0
    for model in aggregator_models:
        r = c.AggregatorSolver().solve(model)        
        if r['Solver']()['Termination condition'] != 'optimal':
            raise AssertionError('Aggregator Solve Failure')
        agg.Write_Prediction_Data(c.aggregators[a], model, t)
        a += 1
    log.info('Aggregator predictive step complete.')
    tp3 = time.time()
    dso_model = dso.build_DSO_OPF(c.feeder,t)
    dso_model = dso.DOE_Step_Solve(dso_model)
    dso.Write_DOEs(dso_model,t,c.feeder)
    
    log.info('DSO steps complete.')
    tp4 = time.time()
    #Update each agg model with DOEs. Solve.
    a = 0
    for model in aggregator_models:
        agg.Add_DOE_Constraints(c.aggregators[a],model,t)
        r = c.AggregatorSolver().solve(model,warmstart=True)
        if r['Solver']()['Termination condition'] != 'optimal':
            r.pprint()
            raise AssertionError('Aggregator with DOE solve failure')
        log.info(f'Aggregator {a+1} solve complete.')
        agg.Write_All_Data(c.aggregators[a], model, t)
        log.info(f'Timestep data written back to dataframes.')
        a += 1   
    
    tp5 = time.time() 
    
    #Write agg summary/key data to ???
    
    #Feed solved P_meter into DSO model. Solve. Validate & record data.
        
    
    
    tloop_end = time.time()
    log.info(f'Loop {loop} complete in {tloop_end - tloop_start}s. \n {(tloop_end-tloop_start)*(len(T)-loop)/3600} hours remaining.')
    loop += 1
    
    timers = {
        'aggregator_model_builds': tp2-tp1,
        'aggregator_solves': tp3-tp2,
        'DSO steps': tp4-tp3,
        'Aggregator resolves': tp5-tp4,
        
        }
    print(timers)
#do_results_reporting_things()
    
        
    