#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Oct  2 17:13:00 2023

@author: marlon
"""
import Configuration as conf
import math as m
import pandas as pd
import logging as log
#import pyomo.environ as pyo

#This script allows interchanging of the info in `Configuration.py` for different inputs, in order to run different experiments from RunExperiments


dso_options = conf.dso_options


feeder = {'is_built': False}

experiment_nioe = {
    'Name': 'No_IOEs',
    'IOEs': 'inactive',
    'DSO Option':     conf.dso_options[0],
    'Rebuild feeder': False,
    'Aggregators': [
            {
              'AggregatorID' : 1,
              'Number of Nodes' : 50,
              'Behaviour' : 'Non-strategic',
              'Nodes' : dict(),
              'Expected Offline Fraction': conf.nu,
              },
            {
              'AggregatorID' : 2,
              'Number of Nodes' : 50,
              'Behaviour' : 'Non-strategic',
              'Nodes': dict(),
              'Expected Offline Fraction' : conf.nu,
              }
        ],
    't_start':  6336,
    'intervals':288,
    
    }

experiment1 = {
    'Name': 'No_Strategic_aggs_v2',
    'IOEs': 'active',
    'DSO Option':     conf.dso_options[0],
    'Rebuild feeder': False,
    'Aggregators': [
            {
              'AggregatorID' : 1,
              'Number of Nodes' : 30,
              'Behaviour' : 'Non-strategic',
              'Nodes' : dict(),
              'Expected Offline Fraction': conf.nu,
              },
            {
              'AggregatorID' : 2,
              'Number of Nodes' : 30,
              'Behaviour' : 'Non-strategic',
              'Nodes': dict(),
              'Expected Offline Fraction' : conf.nu,
              }
        ],
    't_start':  6336,
    'intervals':288,
    
    }

experiment2 = {
    'Name': 'Agg2_is_Strategic_v2',
    'IOEs': 'active',
    'DSO Option':     conf.dso_options[0],
    'Rebuild feeder': False,
    'Aggregators': [
            {
              'AggregatorID' : 1,
              'Number of Nodes' : 30,
              'Behaviour' : 'Non-strategic',
              'Nodes' : dict(),
              'Expected Offline Fraction': conf.nu,
              },
            {
              'AggregatorID' : 2,
              'Number of Nodes' : 30,
              'Behaviour' : 'Strategic',
              'Nodes': dict(),
              'Expected Offline Fraction' : conf.nu,
              }
        ],
    't_start':  6336,
    'intervals':288,
    
    }

experiment3 = {
    'Name': 'Agg1_is_Strategic_v2',
    'IOEs': 'active',
    'DSO Option':     conf.dso_options[0],
    'Rebuild feeder': False,
    'Aggregators': [
            {
              'AggregatorID' : 1,
              'Number of Nodes' : 30,
              'Behaviour' : 'Strategic',
              'Nodes' : dict(),
              'Expected Offline Fraction': conf.nu,
              },
            {
              'AggregatorID' : 2,
              'Number of Nodes' : 30,
              'Behaviour' : 'Non-strategic',
              'Nodes': dict(),
              'Expected Offline Fraction' : conf.nu,
              }
        ],
    't_start':  6336,
    'intervals':288,
    
    }

experiment4 = {
    'Name': 'Both_Strategic_v2',
    'IOEs': 'active',
    'DSO Option':     conf.dso_options[0],
    'Rebuild feeder': False,
    'Aggregators': [
            {
              'AggregatorID' : 1,
              'Number of Nodes' : 30,
              'Behaviour' : 'Strategic',
              'Nodes' : dict(),
              'Expected Offline Fraction': conf.nu,
              },
            {
              'AggregatorID' : 2,
              'Number of Nodes' : 30,
              'Behaviour' : 'Strategic',
              'Nodes': dict(),
              'Expected Offline Fraction' : conf.nu,
              }
        ],
    't_start':  6336,
    'intervals':288,
    }


experiments = [experiment_nioe,experiment2,experiment1,experiment4,experiment3]










#######Tools below here are work in progress ###################





def aggregator_wizard(aggid,default=None):
    print(f'Lets build aggregator {aggid}.')
    if default == None:
        print('This is the first aggregator being built, so you must enter the following values.')
        n_nodes = int(input('How many nodes for this aggregator? \n'))
        
        behaviour = int(input("What kind of behaviour? Enter 0 for 'Non-strategic' or 1 for 'Strategic'. \n"))
        
        if behaviour == 0:
            behaviour = 'Non-strategic'
        elif behaviour == 1:
            behaviour = 'Strategic'
        else:
            raise ValueError('Invalid strategy input, must be 0 or 1.')
        
        nu = float(input('Enter offline fraction value (0 - 1): \n'))
        
        assert nu > 0 and nu <= 1
        
        aggregator = {
            'AggregatorID' : aggid,
            'Number of Nodes' : n_nodes,
            'Behaviour' : 'Non-strategic',
            'Nodes': dict(),
            'Expected Offline Fraction' : nu,
            }
        print(aggregator)
        confirm = input('Press enter to continue, or enter any text to retry.')
        if confirm == '':
            return aggregator
        else:
            return aggregator_wizard(aggid,default=default)
    elif type(default) == dict:
        print('For this aggregator, hit enter without entering anything to use the same value as the previous aggregator.')
        n_nodes = int(input('How many nodes for this aggregator? \n'))
        behaviour = int(input("What kind of behaviour? Enter 0 for 'Non-strategic' or 1 for 'Strategic'. \n"))
        if behaviour == 0:
            behaviour = 'Non-strategic'
        elif behaviour == 1:
            behaviour = 'Strategic'
        elif behaviour == '':
            behaviour = default['Behaviour']
        else:
            raise ValueError('Invalid strategy input, must be 0, 1 or nothing.')
        
        nu = float(input('Enter offline fraction value (0 - 1): \n'))
        if nu == '':
            nu = default['Expected Offline Fraction']
        
        assert nu > 0 and nu <= 1
        
        aggregator = {
            'AggregatorID' : aggid,
            'Number of Nodes' : n_nodes,
            'Behaviour' : 'Non-strategic',
            'Nodes': dict(),
            'Expected Offline Fraction' : nu,
            }
        print(aggregator)
        confirm = input('Press enter to continue, or enter any text to retry.')
        if confirm == '':
            return aggregator
        else:
            return aggregator_wizard(aggid,default=default)
    else:
        raise TypeError('something wrong with default agg input')

        

def configuration_wizard(): #NOT COMPLETE
    
    default_dso = 0
    experiments = []
    n_experiments = int(input('How many experiments would you like to configure? \n'))
    
    ex = 1
    for n in range(n_experiments):
        
        print(f'Building Experiment {ex}')
        
        dso_option = input('Choose a DSO option (see Configuration.py, and enter an index): \n')
        
        assert dso_option in range(len(conf.dso_options)), 'out of range dso option index'
        dso_op = conf.dso_options[dso_option]
        aggs = int(input('Number of Aggregators: /n'))
        aggregators = []
        for a in range(aggs):
            if a == 0:
                agg1 = aggregator_wizard(a+1)
                aggregators += [agg1]
            else:
                agg = aggregator_wizard(a+1,default=agg1)
                aggregators += [agg]
        t_start = int(input('What interval do you want to start at:\n'))
        duration = int(input('How many intervals do you want to run through?\n'))
        rebuild_feeder = input('Should the feeder be rebuilt for this experiment?')
        exp = {
            'DSO Option': dso_op,
            'Aggregators': aggregators,
            't_start': t_start,
            'intervals': duration,
            }
            
        experiments += [exp]
        ex += 1
    






