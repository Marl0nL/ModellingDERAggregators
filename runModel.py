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
import utils as u
logger = log.getLogger()
logger.setLevel(log.INFO)
#Setup
start_timer = time.time()
#T = list(range(c.t_start,c.t_end))
T = list(range(c.t_start,c.t_start+288))


if not c.feeder['is_built']:
     prepare.initiate_loads()
     prepare.initiate_aggregators()
     c.feeder = prepare.initiate_feeder(c.aggregators)

#log.info(f'Successfully initiated {len(c.aggregators)} aggregators.')

#Top level process:
results = u.initiate_results_dataframe()
u.pickle_experiment(c.feeder,c.aggregators,'temp')
loop = 1
agg_solver = c.AggregatorSolver()
dso_solver = c.DSOSolver()
for t in T:
    tloop_start = time.time()
    tp1 = time.time()
    aggregator_models = [agg.Aggregator_Model(aggregator, t, mode='prediction') for aggregator in c.aggregators]
    tp2 = time.time()
    a = 0
    for model in aggregator_models:
        r = agg_solver.solve(model)        
        if r['Solver']()['Termination condition'] != 'optimal':
            print(r)
            raise AssertionError('Aggregator Solve Failure')
        agg.Write_Prediction_Data(c.aggregators[a], model, t,IOEs='active')
        a += 1
    log.info('Aggregator predictive step complete.')
    tp3 = time.time()
    dso_model = dso.build_DSO_OPF(c.feeder,t)
    dso_model = dso.DOE_Step_Solve(dso_model,dso_solver)
    dso.Write_DOEs(dso_model,t,c.feeder)
    
    log.info('DSO steps complete.')
    tp4 = time.time()
    #Update each agg model with DOEs. Solve.
    a = 0
    for model in aggregator_models: 
        agg.Add_DOE_Constraints(c.aggregators[a],model,t)
        r = agg_solver.solve(model,warmstart=True)
        if r['Solver']()['Termination condition'] != 'optimal':
            print(r)
            raise AssertionError('Aggregator with DOE solve failure')
        log.info(f'Aggregator {a+1} solve complete.')
        agg.Write_All_Data(c.aggregators[a], model, t)
        log.info(f'Timestep data written back to dataframes.')
        a += 1   
    
    dso.Fix_Actual_Powers(dso_model, t, c.feeder)
    r = dso_solver.solve(dso_model)
    if r['Solver']()['Termination condition'] == 'optimal':
        log.info('DSO final solve is secure and optimal.')
    elif r['Solver']()['Termination conditon'] == 'infeasible':
        log.info('DSO final solve is infeasible.')
        raise AssertionError('check it out, then delete this assertion.')
    
    else:
        print(r)
        raise AssertionError('something odd happened with the final DSO solve.')
    
    tp5 = time.time() 
    
    #Write agg summary/key data to ???
    
    #Feed solved P_meter into DSO model. Solve. Validate & record data.
        
    
    results = u.update_result_data(results,t,dso_model,c.aggregators)
    u.plot_results(results,T,mode='revenue')
    tloop_end = time.time()
    log.info(f'Loop {loop} for t={t} complete in {round(tloop_end - tloop_start,2)}s. \n {round((tloop_end-tloop_start)*(len(T)-loop)/3600,2)} hours remaining.')
    loop += 1
    
    # timers = {
    #     'aggregator_model_builds': tp2-tp1,
    #     'aggregator_solves': tp3-tp2,
    #     'DSO steps': tp4-tp3,
    #     'Aggregator resolves': tp5-tp4,
        
    #     }
    # print(timers)
#do_results_reporting_things()
u.data_dump(results,c.aggregators,T,name='DoubleNonStrategic')
#u.pickle_experiment(c.feeder,c.aggregators,'FinishedDoubleNosdfsdnStrategic')
log.info(f'Dumped data to csvs.')
end_timer = time.time()
log.info(f'Finished run through {len(T)} intervals in {round((end_timer-start_timer)/3600,2)} hours.')        
#c.aggregators[0]['Behaviour'] = 'Strategic'
#c.aggregators[1]['Behaviour'] = 'Strategic'


t = 0

results = u.initiate_results_dataframe()
loop = 1
agg_solver = c.AggregatorSolver()
dso_solver = c.DSOSolver()
for t in T:
    tloop_start = time.time()
    tp1 = time.time()
    aggregator_models = [agg.Aggregator_Model(aggregator, t, mode='prediction') for aggregator in c.aggregators]
    tp2 = time.time()
    a = 0
    for model in aggregator_models:
        r = agg_solver.solve(model)        
        if r['Solver']()['Termination condition'] != 'optimal':
            print(r)
            raise AssertionError('Aggregator Solve Failure')
        agg.Write_Prediction_Data(c.aggregators[a], model, t,IOEs='active')
        a += 1
    log.info('Aggregator predictive step complete.')
    tp3 = time.time()
    dso_model = dso.build_DSO_OPF(c.feeder,t)
    dso_model = dso.DOE_Step_Solve(dso_model,dso_solver)
    dso.Write_DOEs(dso_model,t,c.feeder)
    
    log.info('DSO steps complete.')
    tp4 = time.time()
    #Update each agg model with DOEs. Solve.
    a = 0
    for model in aggregator_models: 
        agg.Add_DOE_Constraints(c.aggregators[a],model,t)
        r = agg_solver.solve(model,warmstart=True)
        if r['Solver']()['Termination condition'] != 'optimal':
            print(r)
            raise AssertionError('Aggregator with DOE solve failure')
        log.info(f'Aggregator {a+1} solve complete.')
        agg.Write_All_Data(c.aggregators[a], model, t)
        log.info(f'Timestep data written back to dataframes.')
        a += 1   
    
    dso.Fix_Actual_Powers(dso_model, t, c.feeder)
    r = dso_solver.solve(dso_model)
    if r['Solver']()['Termination condition'] == 'optimal':
        log.info('DSO final solve is secure and optimal.')
    elif r['Solver']()['Termination conditon'] == 'infeasible':
        log.info('DSO final solve is infeasible.')
        raise AssertionError('check it out, then delete this assertion.')
    
    else:
        print(r)
        raise AssertionError('something odd happened with the final DSO solve.')
    
    tp5 = time.time() 
    
    #Write agg summary/key data to ???
    
    #Feed solved P_meter into DSO model. Solve. Validate & record data.
        
    
    results = u.update_result_data(results,t,dso_model,c.aggregators)
    #u.plot_data(results)
    tloop_end = time.time()
    log.info(f'Loop {loop} for t={t} complete in {round(tloop_end - tloop_start,2)}s. \n {round((tloop_end-tloop_start)*(len(T)-loop)/3600,2)} hours remaining.')
    loop += 1
    
    # timers = {
    #     'aggregator_model_builds': tp2-tp1,
    #     'aggregator_solves': tp3-tp2,
    #     'DSO steps': tp4-tp3,
    #     'Aggregator resolves': tp5-tp4,
        
    #     }
    # print(timers)
#do_results_reporting_things()
u.data_dump(results,c.aggregators,T,name='DoubleStrategic')
#u.pickle_experiment(c.feeder,c.aggregators,'FinishedDoubleSfdsftrategic')
log.info(f'Dumped data to csvs.')
end_timer = time.time()
log.info(f'Finished run through {len(T)} intervals in {round((end_timer-start_timer)/3600,2)} hours.')      


   