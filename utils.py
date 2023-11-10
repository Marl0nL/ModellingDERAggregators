#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Sep 23 22:47:44 2023

@author: marlon
"""
import numpy as np
import pandas as pd
import Configuration as c
from matplotlib import pyplot as plt
import math as m
import logging as log
import time
import os
import pickle

def write_lp(model,fname):
    model.write(filename = fname, format='cpxlp', io_options = {"symbolic_solver_labels":True})


def initiate_results_dataframe(aggregators=c.aggregators):
    columns = ['Max Voltage','Min Voltage','Total Meter Power']
    columns += ['Aggregator'+str(x['AggregatorID'])+'Revenue' for x in aggregators]
    columns += ['Aggregator'+str(x['AggregatorID'])+'Curtailment' for x in aggregators]
    columns += ['Aggregator'+str(x['AggregatorID'])+'Breaches' for x in aggregators]
    
    df = pd.DataFrame(columns=columns)
    df['Max Voltage'] = np.repeat(['None'],c.number_of_intervals)
    return df
def update_result_data(data,t,dso_model,aggregators):
    voltages = []
    for bus in list(dso_model.voltage.index_set()):
        voltages += [dso_model.voltage[bus].value]
    
    max_volt = np.max(voltages)
    min_volt = np.min(voltages)
    
    log.info(f'Voltage range seen: \n Min:{round(min_volt,4)} \n Max:{round(max_volt,4)}')
    
    data['Max Voltage'][t] = max_volt
    data['Min Voltage'][t] = min_volt
    
    meterpowers = []
    for aggregator in aggregators:
        agid = aggregator['AggregatorID']
        rev = sum([aggregator['Nodes'][node]['settled_revenue'][t] for node in aggregator['Nodes'].keys()])
        data['Aggregator'+str(aggregator['AggregatorID'])+'Revenue'][t] = rev
        import_curtailment = sum([(aggregator['Nodes'][node]['upper_IOE'][t] - aggregator['Nodes'][node]['import_DOE'][t] ) for node in aggregator['Nodes'].keys()])#/ (aggregator['Nodes'][node]['upper_IOE'][t]-aggregator['Nodes'][node]['lower_IOE'][t]) for node in aggregator['Nodes'].keys()])
        export_curtailment = sum([(aggregator['Nodes'][node]['export_DOE'][t] - aggregator['Nodes'][node]['lower_IOE'][t] ) for node in aggregator['Nodes'].keys()])#/ (aggregator['Nodes'][node]['upper_IOE'][t]-aggregator['Nodes'][node]['lower_IOE'][t]) for node in aggregator['Nodes'].keys()])
        ubreaches = sum([aggregator['Nodes'][node]['Upper_DOE_Breach'][t] for node in aggregator['Nodes'].keys()])
        lbreaches = sum([aggregator['Nodes'][node]['Lower_DOE_Breach'][t] for node in aggregator['Nodes'].keys()])
        data['Aggregator'+str(aggregator['AggregatorID'])+'Curtailment'][t] = import_curtailment+export_curtailment
        data['Aggregator'+str(aggregator['AggregatorID'])+'Breaches'][t] = ubreaches+lbreaches
        log.info(f'Aggregator {agid} key data: \n Import Curtailment: {round(import_curtailment,3)} \n Export Curtailment: {round(export_curtailment,3)} \n Revenue: {round(rev,4)} \n Upper Breaches: {ubreaches} \n Lower Breaches: {lbreaches}')
        meterpowers += [sum([aggregator['Nodes'][node]['P_meter'][t] for node in aggregator['Nodes'].keys()])]
    
    data['Total Meter Power'][t] = sum(meterpowers)
    log.info(f'Total Meter Power: {round(sum(meterpowers),2)} kW')
    
    return data


def plot_results(data,T,mode='all'):
    data = data.iloc[T]
    if mode == 'all':
        for column in data.columns:
            plt.plot(data[column], label=column)
            
    elif mode == 'revenue':
        for column in ['Aggregator1Revenue','Aggregator2Revenue']:
            
            plt.plot(np.cumsum(data[column]), label=column)
            plt.ylabel('Cumulative Revenue ($)')
    plt.plot(np.cumsum(data['Aggregator1Revenue']-data['Aggregator2Revenue']), label='Discrepancy (in favour of Agg1)')
    plt.xlabel('Interval')
    
    plt.legend()
    plt.show()
    
    
def data_dump(results,aggregators,T,name=''):
    ts = str(int(m.floor(time.time())))
    
    for aggregator in aggregators:
        folder = 'results/'+name+'_Aggregator'+str(aggregator['AggregatorID'])+'_'+ts
        if not os.path.exists(folder):
            os.mkdir(folder)
    
    res_name = 'results/'+name+'_result_'+ts+'.csv'
    results.iloc[T].to_csv(res_name)
    for aggregator in aggregators:
        folder = 'results/'+name+'_Aggregator'+str(aggregator['AggregatorID'])+'_'+ts
        for node in aggregator['Nodes'].keys():
            aggregator['Nodes'][node].iloc[T].to_csv(folder+'/node'+str(node)+'.csv')
    

        
def pickle_feeder(feeder,fname):
    with open(fname,'wb') as f:
        pickle.dump(feeder, f)
        f.close()
    log.info(f'Pickled feeder to {fname}')

def unpickle_feeder(fname):
    with open(fname,'rb') as f:
        feeder = pickle.load(f)
        f.close()
    return feeder

def pickle_aggregators(agglist,fname):
    with open(fname,'wb') as f:
        pickle.dump(agglist,f)
        f.close()

def unpickle_aggregators(fname):
    with open(fname,'rb') as f:
        agglist = pickle.load(f)
        f.close()
    return agglist

def pickle_experiment_metadata(experiment,fname):
    with open(fname,'wb') as f:
        pickle.dump(experiment,f)
        f.close()


def pickle_experiment(feeder,agglist,name,experiment):
    directory = 'experiments/'+name
    if not os.path.exists(directory):
        os.mkdir(directory)
    
    pickle_feeder(feeder,directory+'/feeder.pkl')
    pickle_aggregators(agglist,directory+'/aggregators.pkl')
    pickle_experiment_metadata(experiment,directory+'/metadata.pkl')
    log.info(f'Experiment configuration {name} has been pickled.')
    
def unpickle_experiment(name):
    aggs = unpickle_aggregators('experiments/'+name+'/aggregators.pkl')
    feeder = unpickle_feeder('experiments/'+name+'/feeder.pkl')
    
    for a in aggs: #Re-link the node dataframes references by the feeder and the aggregators.
        for n in a['Nodes'].keys():
            name = (a['AggregatorID'],n)
            feeder['nodes'][name]['data'] = a['Nodes'][n]
    
    return feeder, aggs

def graph_average_node(aggregator,T):
    columns = ['P_meter','P_solar','P_load','P_batt']
    
    frames = list(aggregator['Nodes'].values())
    def itersum(l):
        if len(l) == 1:
            return l[0]
        else:
            return l[0]+itersum(l[1:])
    data = itersum(frames).iloc[T][columns]/len(frames)

    plt.plot(data['P_solar'], color='orange', label='P_Solar')
    plt.plot(data['P_meter'], color='blue', label='P_Meter')
    plt.plot(data['P_batt'], color='red', label='P_Battery')
    plt.plot(data['P_load'], color='green', label='P_Load')
    plt.xlabel('Interval')
    plt.ylabel('Power (kW)')
    plt.legend()
    plt.show()    
   
            
            
    
