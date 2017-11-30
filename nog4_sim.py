from DetectorResponseGaussAngle import DetectorResponseGaussAngle
from EventAnalyzer import EventAnalyzer
from chroma.detector import Detector, G4DetectorParameters
from chroma.sim import Simulation
import time, h5py, os, argparse
import lensmaterials as lm
import kabamland2 as kbl

import numpy as np
from pprint import pprint

from Geant4.hepunit import *

import paths

def fixed_dist(sample, radius, in_shell, out_shell, rads=None):
	loc1 = sph_scatter(sample,in_shell,out_shell)
	loc2 = sph_scatter(sample,in_shell,out_shell)
	if rads == None:
		rads = np.linspace(50,500,sample)
	else:
		rads = np.full(sample,rads)
	dist = loc1-loc2
	loc2 = loc1 + np.einsum('i,ij->ij',rads,dist/np.linalg.norm(dist,axis=1)[:,None])
	bl_idx = np.linalg.norm(loc2,axis=1)>radius
	loc2[bl_idx] = 2 * loc1[bl_idx] - loc2[bl_idx]
	return loc1,loc2,rads

def sph_scatter(sample,in_shell,out_shell):
	print('sph_scatter shell radii: ' + str(in_shell) + ' ' + str(out_shell))
	loc = np.random.uniform(-out_shell,out_shell,(sample,3))
	while len(loc[(np.linalg.norm(loc,axis=1)>in_shell) & (np.linalg.norm(loc,axis=1)<=out_shell)]) != sample:
		bl_idx = np.logical_not((np.linalg.norm(loc,axis=1)>in_shell) & (np.linalg.norm(loc,axis=1)<=out_shell))
		smpl = sum(bl_idx)
		loc[bl_idx] = np.random.uniform(-out_shell,out_shell,(smpl,3))
	return loc

def create_double_source_events(locs1, locs2, sigma, amount1, amount2):
	# produces a list of Photons objects, each with two different photon sources
	# locs1 and locs2 are lists of locations (tuples)
	# other parameters are single numbers
	events = []
	if len(locs1.shape) == 1:
		locs1 = locs1.reshape((1,-1))
		locs2 = locs2.reshape((1,-1))
	for loc1,loc2 in zip(locs1,locs2):
		event1 = kbl.gaussian_sphere(loc1, sigma, int(amount1))
		event2 = kbl.gaussian_sphere(loc2, sigma, int(amount2))
		event = event1 + event2						#Just add the list of photons from the two sources into a single event
		events.append(event)
	return events

def sim_setup(config,in_file, useGeant4=False, cuda_device=None):
	g4_detector_parameters = G4DetectorParameters(orb_radius=7., world_material='G4_Galactic') if useGeant4 else None
	kabamland = kbl.load_or_build_detector(config, lm.create_scintillation_material(), g4_detector_parameters=g4_detector_parameters)
	sim = Simulation(kabamland,geant4_processes = 4 if useGeant4 else 0, cuda_device=cuda_device)
	det_res = DetectorResponseGaussAngle(config,10,10,10,in_file)
	analyzer = EventAnalyzer(det_res)
	return sim, analyzer

# Runs the simulation and writes the HDF5 file (except the index)
def run_simulation(file, sim, events, analyzer, first=False):
	arr = []
	for ev in sim.simulate(events, keep_photons_beg = True, keep_photons_end = True, run_daq=False, max_steps=100):
		tracks = analyzer.generate_tracks(ev,qe=(1./3.))
                print("Track count: " + str(len(tracks)))
		#pprint(vars(ev))
		#pprint(vars(tracks))
                '''
		print('Firing particle name/photon count/track count/location/direction: \t' +  # Add energy
                      'photons' + '\t' + # ev.primary_vertex.particle_name + '\t' +
                      str(len(ev.photons_beg)) + '\t' +
		      str(len(tracks)) + '\t' +
	              #str(ev.primary_vertex.pos) + '\t' +
                      #str(ev.primary_vertex.dir) + '\t'
                      '')
		print('Photons begin count, track count:\t' + str(len(ev.photons_beg)) + '\t' + str(len(tracks)))
		'''
                if first:
			coord = file.create_dataset('coord', maxshape=(2,None,3), data=[tracks.hit_pos.T, tracks.means.T],chunks=True)
			uncert = file.create_dataset('sigma', maxshape=(None,), data=tracks.sigmas,chunks=True)
			arr.append(tracks.sigmas.shape[0])
			file.create_dataset('r_lens',data=tracks.lens_rad)
                else:
			coord = file['coord']
			uncert = file['sigma']
			coord.resize(coord.shape[1]+tracks.means.shape[1], axis=1)
			coord[:,-tracks.means.shape[1]:,:] = [tracks.hit_pos.T, tracks.means.T]
			uncert.resize(uncert.shape[0]+tracks.sigmas.shape[0], axis=0)
			uncert[-tracks.sigmas.shape[0]:] = tracks.sigmas
			arr.append(uncert.shape[0])
	return arr

def fire_photons_single_site(sample,amount,sim,analyzer,in_shell,out_shell,sigma=0.01):
        arr = []
        first = True
        location = sph_scatter(sample,in_shell,out_shell)
        fname = seed_loc+'s-site.h5'
        if not os.path.exists(data_file_dir):
                os.makedirs(data_file_dir)
        file_path = data_file_dir+fname
        with h5py.File(file_path,'w') as f:
                for lg in location:
                        gun = kbl.gaussian_sphere(lg, sigma, amount)
                        arr.extend(run_simulation(f, sim, gun, analyzer, first))
                        first = False
                f.create_dataset('idx',data=arr)

def fire_photons_double_site(sample,amount,sim,analyzer,in_shell,out_shell,dist,sigma=0.01):
        arr = []
        first = True
        locs1, locs2, rad = fixed_dist(sample,5000,in_shell,out_shell,rads=dist)
        fname = seed_loc+'d-site'+str(int(dist/10))+'cm.h5'
        if not os.path.exists(data_file_dir):
                os.makedirs(data_file_dir)
        file_path = data_file_dir+fname
        with h5py.File(file_path,'w') as f:
                for lc1,lc2 in zip(locs1,locs2):
                        gun = create_double_source_events(lc1, lc2, sigma, amount/2, amount/2)
                        arr.extend(run_simulation(f, sim, gun, analyzer, first))
                        first = False
                f.create_dataset('idx',data=arr)

from chroma.sample import uniform_sphere

def myhack():
    while True:
        yield uniform_sphere()
        #yield [-1,0,0]

def fire_particles(particle_name,sample,energy,sim,analyzer,sigma=0.01):
	arr = []
	first = True
	# KW? fname = particle_name+'.h5'
	location = sph_scatter(sample,in_shell,out_shell)
	fname = 's-site.h5'
	with h5py.File(path+fname,'w') as f:
		for lg in location:     # x in np.linspace(0., 1000., num=20):
			#lg = [7000.,0,0]
			# direction = [-1,0,0]
			# Direction original code is: vertex.isotropic()
			gun = vertex.particle_gun([particle_name], vertex.constant(lg), vertex.isotropic(), vertex.flat(float(energy) * 0.99, float(energy) * 1.01))
			# gun = vertex.particle_gun([particle_name], vertex.constant(lg), myhack(), vertex.flat(float(energy) * 0.99, float(energy) * 1.01))
			arr.extend(run_simulation(f, sim, gun, analyzer, first))
			first = False
		f.create_dataset('idx',data=arr)

energy = 1.

if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('cfg', help='detector configuration')
	parser.add_argument('sl', help='seed_location')
	args = parser.parse_args()
	sample = 500
	distance = np.linspace(20,450,6)
	cfg = args.cfg
	seed_loc = args.sl
	in_shell = int(seed_loc[0])*1000
	out_shell = int(seed_loc[1])*1000
	print('Seed locations: ' + str(in_shell) + ' ' + str(out_shell))
	data_file_dir = paths.get_data_file_path(cfg)
	start_time = time.time()
	sim,analyzer = sim_setup(cfg,paths.get_calibration_file_name(cfg))
	print 'configuration loaded in %0.2f' %(time.time()-start_time)
	amount = 16000
	fire_photons_single_site(sample, amount, sim, analyzer, in_shell, out_shell)
	print 's-site done'
	for dst in distance:
		fire_photons_double_site(sample,16000,sim,analyzer, in_shell, out_shell, dst)
		print 'distance '+str(int(dst/10))+' done'


	'''
	print('Firing ' + str(energy) + ' MeV e-''s')
	fire_particles('e-', sample, energy*MeV, sim, analyzer)
	print('Firing ' + str(energy) + ' MeV gammas')
	fire_particles('gamma', sample, energy*MeV, sim, analyzer)
        '''
	'''
	bkg_dist_hist(sample,16000,sim,analyzer)
	print 's-site done'
	for dst in distance:
		fixed_dist_hist(dst,sample,16000,sim,analyzer)
		print 'distance '+str(int(dst/10))+' done'
	'''
	print time.time()-start_time

