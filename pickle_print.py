#!/c/Program Files/Python36/python

import pprint
import pickle
import numpy as np
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('pickle_file', help='Pickle file name')
args = parser.parse_args()

with open(args.pickle_file, 'rb') as f:
    # The protocol version used is detected automatically, so we do not have to specify it.
    data = pickle.load(f)
    np.set_printoptions()  # threshold=np.inf)  # In order to get the full arrays
    if data is not None:
        if 'acquisition_parameters' in data:    # Special case for DM Radio
            pprint.pprint(data.acquisition_parameters.__dict__)
        if '__dict__' in data:
            pprint.pprint(data.__dict__)
        else:
            pprint.pprint(data)
    else:
        print("No data in file: " + args.pickle_file)
