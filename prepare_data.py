#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Aug 26 20:57:37 2023

@author: marlon
"""
import math as m
import pandas as pd
pd.options.mode.chained_assignment = None  # default='warn'
import numpy as np
import csv
import Configuration as conf
import logging as log
import multiprocessing as mp

def loop_scaler(column,length): #Makes a list (column) the desired length.
    column = list(column)
    if len(column) == length:
        return column
    elif len(column) > length:
        return column[0:length]
    elif len(column) < length:
        loop_factor = int(m.ceil(length/len(column)))
        looped = column*loop_factor
        trim = looped[0:length]
        return trim
    
        
def initiate_node(agg,
                  intervals=conf.number_of_intervals, 
                  aggregator_inputs=conf.aggregator_inputs,
                  nu=conf.nu):
    t_start = conf.t_start
    
    node = pd.DataFrame()
    
    node['solar'] = 1*aggregator_inputs['solar_profiles'][ #the column with name...
        aggregator_inputs['solar_profiles'].columns[ #indexed by random index in range.
        np.random.randint(0,len(aggregator_inputs['solar_profiles'].columns))]][0:intervals] 
    node['P_solar_max'] = [0 for t in range(intervals)]
    node['P_solar_min'] = [m.floor(node['solar'].min()) for n in range(intervals)]
    
    node['P_load'] = 0.9*aggregator_inputs['load_profiles'][ #the column with name...
        aggregator_inputs['load_profiles'].columns[ #indexed by random index in range.
        np.random.randint(0,len(aggregator_inputs['load_profiles'].columns))]]
    node['load_min'] = [0.0 for t in range(intervals)]
    if node['P_load'].max() > 28.0:
        node['load_max'] = [43.5 for t in range(intervals)] #3phase 63A supply.
    elif node['P_load'].max() > 15.0:
        node['load_max'] = [28.0 for t in range(intervals)] #3ph/40A
    elif np.random.randint(1,5) > 4:
        node['load_max'] = [28.0 for t in range(intervals)] #underused 3ph
    else:
        node['load_max'] = [15.0 for t in range(intervals)] #63A 1ph.
        
    battery = aggregator_inputs['batteries'][aggregator_inputs['batteries'].columns[np.random.randint(1,len(aggregator_inputs['batteries'].columns))]]
    node['SOC_min'] = [battery[0] for t in range(intervals)]
    node['SOC_max'] = [battery[1] for t in range(intervals)]
    node['P_batt_max'] = [battery[2] for t in range(intervals)]
    node['P_batt_min'] = [battery[3] for t in range(intervals)]
    node['battery_eta'] = [battery[4] for t in range(intervals)]
    
    
    node['import_price'] = loop_scaler(aggregator_inputs['tariff']['import_price'],intervals)
    node['export_price'] = loop_scaler(aggregator_inputs['tariff']['export_price'],intervals)
    
    node['raise_price'] = loop_scaler(aggregator_inputs['fcas_prices']['raise_price'],intervals)
    node['lower_price'] = loop_scaler(aggregator_inputs['fcas_prices']['lower_price'],intervals)
    
    #node['raise_price'] = [0.0 for t in range(intervals)]
    #node['lower_price'] = [0.0 for t in range(intervals)]
    
    node['nu'] = [nu for t in range(intervals)]
    
    #Empty columns to be populated:
    l = len(node.index)
    node['P_solar'] = [None]*l
    node['P_meter'] = [None]*l
    node['P_batt'] = [None]*l
    node['SOC'] = [None]*l
    node['Online'] = [None]*l
    
    
    node['import_DOE'] = [None]*l
    node['export_DOE'] = [None]*l
    node['upper_IOE'] = [None]*l
    node['lower_IOE'] = [None]*l
    node['Upper_DOE_Breach'] = [None]*l
    node['Lower_DOE_Breach'] = [None]*l
    
    node['settled_revenue'] = [None]*l
    node['aggregator'] = [agg['AggregatorID']]*l
    node['R_bid'] = [None]*l
    node['L_bid'] = [None]*l
    #Set Initial State Values:
    node['upper_IOE'][t_start-1] = node['load_max'][t_start-1]+node['P_batt_max'][t_start-1]
    node['lower_IOE'][t_start-1] = node['P_solar_min'][t_start-1] + node['P_batt_min'][t_start-1]
    node['import_DOE'][t_start-1] = node['upper_IOE'][t_start-1]
    node['export_DOE'][t_start-1] = node['lower_IOE'][t_start-1]
    node['Online'][t_start-1] = 1
    node['P_batt'][t_start-1] = 0.0
    node['R_bid'][t_start-1] = 0.0
    node['L_bid'][t_start-1] = 0.0
    node['Upper_DOE_Breach'][t_start-1] = 0
    node['Lower_DOE_Breach'][t_start-1] = 0
    init_solar = node['solar'][t_start-1]
    node['P_solar'][t_start-1] = init_solar
    init_meter = node['P_batt'][t_start-1] + node['P_solar'][t_start-1] + node['P_load'][t_start-1]
    node['P_meter'][t_start-1] = init_meter
    init_soc = np.random.randint(1000*node['SOC_min'][0],m.ceil(600*node['SOC_max'][t_start-1]))/1000
    node['SOC'][t_start-1] = init_soc
    
    return node
        
def initiate_loads(load_config=conf.load_nodes,aggregator_inputs = conf.aggregator_inputs):
    load_count = load_config['Number of Nodes']
    c = 0
    while len(load_config['Nodes']) < load_count:
        
        load = pd.DataFrame()
        load['P_load'] = aggregator_inputs['load_profiles'][ #the column with name...
            aggregator_inputs['load_profiles'].columns[ #indexed by random index in range.
            np.random.randint(0,len(aggregator_inputs['load_profiles'].columns))]]
        load_id = c
        c += 1
        load_config['Nodes'][load_id] = load
    
    log.info(f'{c} uncontrolled loads initiated.')
    return load_config

def initiate_aggregator(aggregator,
                        agg_input = conf.aggregator_inputs):
    node_count = aggregator['Number of Nodes']
    agg_id = aggregator['AggregatorID']
    c = 0
    while len(aggregator['Nodes'].keys()) < node_count:
        n = initiate_node(aggregator)
        node_id = c #Could make this a string, or even encode extra info, if desired.
        aggregator['Nodes'][node_id] = n 
        c += 1
        log.debug(f'Node {c} created.')
        
    log.info(f'All nodes for aggregator {agg_id} initiated.')
    return aggregator
    #return aggregatorrom some of the smartest 

def initiate_aggregators(): #parallelised initiation of all aggs.
    pool = mp.Pool(processes=len(conf.aggregators),initializer=np.random.seed())
    result = pool.map(initiate_aggregator,conf.aggregators)
    conf.aggregators = result
    del result

def initiate_feeder(aggregators,dso_inputs=conf.dso_inputs,loads=conf.load_nodes):
    node_count = sum(len(a['Nodes'].keys()) for a in aggregators)+loads['Number of Nodes']
    feeder = dict()
    feeder['buses'] = dso_inputs['buses']
    feeder['lines'] = dso_inputs['lines']
    feeder['V_ref'] = dso_inputs['V_ref']
    
    #Set base units for per unit calculations
    feeder['V_base'] = feeder['buses']['vn_kv'][0] * 1000 # V
    feeder['S_base'] = 1000000 # VA / MVA
    feeder['I_base'] = feeder['S_base']/(np.sqrt(3)*feeder['V_base'])
    feeder['Z_base'] = feeder['V_base']**2 / feeder['S_base']
    
    #Scale values to match per-unit system
    feeder['lines']['r'] = feeder['lines']['r_ohm'] / feeder['Z_base']
    feeder['lines']['x'] = feeder['lines']['x_ohm'] / feeder['Z_base']
    feeder['lines']['max_i']  = feeder['lines']['max_i_ka'] * 1000 / feeder['I_base']
    
    feeder['lines'].drop(columns=['r_ohm','x_ohm','max_i_ka'], inplace=True)
    
    _buslist = list(dso_inputs['buses'].index)
    buscount = len(_buslist)
    
    buslist = np.repeat(_buslist[1:],m.ceil(node_count/buscount))
    
    linelist = list(dso_inputs['lines'].index)    
    
    load_dict = {}
    for load in loads['Nodes'].keys():
        name = int(load)
        np.random.seed()
        np.random.shuffle(buslist)
        load_dict[name] = {
            'data': loads['Nodes'][load],
            'location': np.random.choice(buslist),
            }
    
    feeder['loads'] = load_dict
    

    nodes = {} #Build a nodelist from all aggregator nodes, and assign bus locations to nodes.
    for a in aggregators:
        for n in a['Nodes'].keys():
            name = (a['AggregatorID'],n)
            np.random.seed()
            nodes[name] = {
                    'data' : a['Nodes'][n],
                    'location': np.random.choice(buslist),
                    }
                               
    
    feeder['nodes'] = nodes
    
    

    #Create bus-based lookup dictionaries
    lookup_nodes = dict()
    lookup_loads = dict()
    lookup_lines = dict()
    lookup_adjacent_buses = dict()
    name_bus_tuples = [(n,nodes[n]['location']) for n in nodes.keys()]
    
    for bus in feeder['buses'].index:
        lookup_loads[bus] = [load for load in feeder['loads'].keys() if feeder['loads'][load]['location'] == bus]
        lookup_nodes[bus] = [node[0] for node in name_bus_tuples if node[1] == bus]
        to = [x for x in feeder['lines'].index if feeder['lines'].loc[x]['to_bus'] == feeder['buses'].loc[bus]['id']]
        from_ = [x for x in feeder['lines'].index if feeder['lines'].loc[x]['from_bus'] == feeder['buses'].loc[bus]['id']]
        lookup_lines[bus] = {
                'to'    : to,
                'from'  : from_,
                }
        
        adjacent_buses = []
        for line in lookup_lines[bus]['to']:
            adjacent_buses += [feeder['lines']['from_bus'][line]]
        for line in lookup_lines[bus]['from']:
            adjacent_buses += [feeder['lines']['to_bus'][line]]
        
        lookup_adjacent_buses[bus] = adjacent_buses
        
    feeder['lookup_loads'] = lookup_loads
    feeder['lookup_nodes'] = lookup_nodes
    feeder['lookup_lines'] = lookup_lines
    feeder['lookup_adj_buses'] = lookup_adjacent_buses
    feeder['is_built'] = True
    log.info('Feeder initialised successfully.')
    return feeder
    
       
if __name__ == "__main__":
    print('Running test of aggregator and feeder initialisation.')
    initiate_loads()
    initiate_aggregators()
    feeder = initiate_feeder(conf.aggregators)   
    print('Test complete.')
       
    
    
    
        
