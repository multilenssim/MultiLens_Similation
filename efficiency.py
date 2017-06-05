if __name__ == '__main__':
    from DetectorResponse import DetectorResponse
    from DetectorResponsePDF import DetectorResponsePDF
    from DetectorResponseGaussAngle import DetectorResponseGaussAngle
    from ShortIO.root_short import ShortRootReader
    from EventAnalyzer import EventAnalyzer
    import kabamland2 as kbl
    import lensmaterials as lm
    from chroma.sample import uniform_sphere
    from chroma.detector import Detector
    from chroma.sim import Simulation
    from chroma.loader import load_bvh
    from chroma.event import Photons
    from chroma import make, view, sample
    import numpy as np
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import axes3d
    from matplotlib import rcParams
    from matplotlib import cm
    import detectorconfig
    import math
    from array import array
    import ROOT
    import sys, getopt, time, os, datetime
    
    datadir = "/home/exo/"
    rootdir = "/home/exo/Dropbox/Kabamland/efficiency/"
    now = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    
    def eff_test(config, detres=None, detbins=10, sig_pos=0.01, n_ph_sim=[6600], repetition=10, max_rad=6600, n_pos=10, loc1=(0,0,0), sig_cone=0.01, lens_dia=None, n_ph=0, min_tracks=0.05, chiC=3., temps=[256, 0.25], tol=0.1, debug=False):
		###############################################
		
        run = array('i', [0])	# repetition
        pos = array('i', [0])	# n_pos: number of steps 
        xpos_true = array('f', [0])
        ypos_true = array('f', [0])
        zpos_true = array('f', [0])
        xpos = array('f', [0])
        ypos = array('f', [0])
        zpos = array('f', [0])
        multiplicity = array('i', [0])
        photon_sim = array('i', [0])
        photon_true = array('i', [0])
        dist_event = array('f', [0])
        
        ROOT.gROOT.Reset()
        #f1 = ROOT.TFile(rootdir+str(now)+"_"+config+"_rep-"+str(repetition)+"_npos-"+str(n_pos)+".root", "RECREATE") 
        f1 = ROOT.TFile(rootdir+config+"_rep-"+str(repetition)+"_npos-"+str(n_pos)+".root", "RECREATE") 
        ttree = ROOT.TTree("data","data")
        
        ttree.Branch("run", run, "run/I")
        ttree.Branch("pos", pos, "pos/I")
        ttree.Branch("xpos_true", xpos_true, "xpos_true/F")
        ttree.Branch("ypos_true", ypos_true, "ypos_true/F")
        ttree.Branch("zpos_true", zpos_true, "zpos_true/F")
        ttree.Branch("xpos", xpos, "xpos/F")
        ttree.Branch("ypos", ypos, "ypos/F")
        ttree.Branch("zpos", zpos, "zpos/F")
        ttree.Branch("dist_event", dist_event, "dist_event/F")
        ttree.Branch("photon_sim", photon_sim, "photon_sim/I")	
        ttree.Branch("photon_true", photon_true, "photon_true/I")	
        ttree.Branch("multiplicity", multiplicity, "multiplicity/I")	
       
		# Build detector 
        kabamland = Detector(lm.ls)
        kbl.build_kabamland(kabamland, config)
        kabamland.flatten()
        kabamland.bvh = load_bvh(kabamland)
        #view(kabamland)
        #quit()

        sim = Simulation(kabamland)
        print "Simulation started."

        if detres is None:
            det_res = DetectorResponseGaussAngle(config, detbins, detbins, detbins)
        else:
            det_res = DetectorResponseGaussAngle(config, detbins, detbins, detbins, infile=(datadir+detres))
        analyzer = EventAnalyzer(det_res)
        
        # Previous definition of rads 
        #rads = [max_rad*float(ii+1)/n_pos for ii in range(n_pos)]
        
        # Get radius for equal volumes within the detector up to the maximum radius max_rad 
        #rads = radius_equal_vol(max_rad = max_rad, steps = n_pos)
        
        # Get equally seperated radii within the detector up to the maximum radius max_rad
        rads = [ii*max_rad/n_pos for ii in range(n_pos+1)]
        
        recon = np.zeros((len(n_ph_sim), repetition, n_pos+1, 6))
        
        for ii, amount in enumerate(n_ph_sim):	
			for iy, rad in enumerate(rads):
				print "Energy: " + str(amount) + ", radius: " + str(rad)
					
				events, points = create_single_source_events(rad, sig_pos, amount, repetition)	
				
				for ind, ev in enumerate(sim.simulate(events, keep_photons_beg = True, keep_photons_end = True, run_daq=False, max_steps=100)):
					
					# Do AVF event reconstruction
					vtcs = analyzer.analyze_one_event_AVF(ev, sig_cone, n_ph, min_tracks, chiC, temps, tol, debug, lens_dia)
					
					# Weight vertices by n_ph
					doWeights = True 
					
					# Append results unless no vertices were found
					if vtcs: 
						
						photons = [vtx.n_ph for vtx in vtcs]
						n_ph_total = np.sum(photons)
						n_ph_max = np.max(photons)  
						event_pos = points[ind,:]
						
						if event_pos is not None:
							min_errs = []
							weights = []
							for ii, vtx in enumerate(vtcs):
								
								#Skip vertex with smaller amount of photon tracks associated with 
								if ii != np.argmax(n_ph_total):
									print "Two vertices found! Smaller vertex with ", photons[ii],"photons out of ", n_ph_total
									break
									
								# Skip vertices outside detector
								if np.linalg.norm(vtx.pos) > det_res.inscribed_radius: 
									break 
								
								# Get distances to true source locs
								errs = vtx.pos - event_pos 
								
								# Get reconstruced radius 
								r_recon = np.sqrt(vtx.pos[0]*vtx.pos[0]+vtx.pos[1]*vtx.pos[1]+vtx.pos[2]*vtx.pos[2])
								
								# Get distance to true event location 
								vtx_dist = np.sqrt(errs[0]*errs[0]+errs[1]*errs[1]+errs[2]*errs[2])
									
								recon[ii,ind,iy,:] = [rad/10, r_recon/10, n_ph_total, errs[0], errs[1], errs[2]]
								
								# Fill TTree 
								run[0] = ind
								pos[0] = iy
								xpos_true[0] = event_pos[0]
								ypos_true[0] = event_pos[1]
								zpos_true[0] = event_pos[2]
								xpos[0] = vtx.pos[0]
								ypos[0] = vtx.pos[1]
								zpos[0] = vtx.pos[2]
								multiplicity[0] = len(vtcs)
								photon_sim[0] = amount
								photon_true[0] = n_ph_total
								dist_event[0] = vtx_dist
								#print run[0], pos[0], xpos_true[0], ypos_true[0], zpos_true[0], xpos[0], ypos[0], zpos[0], multiplicity[0], photon_sim[0], photon_true[0], dist_event[0]
								#print iy, ind, r_recon, vtx_dist, float(n_ph_total)/float(amount), len(vtcs)
								ttree.Fill()
        f1.Write()
        f1.Close()							
        plot_double_yaxis(recon, n_ph_sim, n_pos, max_rad)
        
    def create_single_source_events(rad, sigma, amount, repetition):
        # produces a list of photon objects on the surface of a spherical shell with a fixed radius 
		events = []
		points = np.zeros((repetition, 3))
		for x in range(repetition):
			theta = np.arccos(np.random.uniform(-1.0, 1.0))
			phi = np.random.uniform(0.0, 2*np.pi)
			points[x,0] = rad*np.sin(theta)*np.cos(phi)
			points[x,1] = rad*np.sin(theta)*np.sin(phi)
			points[x,2] = rad*np.cos(theta)
			event = kbl.gaussian_sphere(points[x,:], sigma, amount)
			events.append(event)
		return events, points 


    def plot_double_yaxis(recon, n_ph_sim, n_pos, max_rad):
		# Create double y-axis plot with position resolution shown on the left side in blue and the light collection efficiency on the right side in red 
		
		# Create axis object for plotting
		ax1 = plt.gca()
		
		ax2 = ax1.twinx()
		
		ax1.set_xlabel('Radius [cm]')
		ax1.set_ylabel('Position Resolution [mm]', color='blue')
		ax2.set_ylabel('Light Collection Efficiency', color='red')
        
		ax1.set_xlim(-100, max_rad*1.1/10)
		ax1.set_ylim(0, 400)
		ax2.set_ylim(0, .35)
        
		for zz, amount in enumerate(n_ph_sim):
			for ii in range(n_pos+1):
				distance = np.sqrt(recon[zz,:,ii,3]*recon[zz,:,ii,3] + recon[zz,:,ii,4]*recon[zz,:,ii,4] + recon[zz,:,ii,5]*recon[zz,:,ii,5])
				distance_mean = np.mean(distance[:])
				ax1.scatter(recon[zz,0,ii,0], distance_mean, color="blue")
				ax1.errorbar(recon[zz,0,ii,0], distance_mean, yerr=np.std(distance[:]), linestyle="None", color="blue")

		for zz, amount in enumerate(n_ph_sim):
			for ii in range(n_pos+1):
				ax2.scatter(recon[zz,0,ii,0],np.mean(recon[zz,:,ii,2]/float(amount)), color="red")
				ax2.errorbar(recon[zz,0,ii,0], np.mean(recon[zz,:,ii,2]/float(amount)), yerr=np.std(recon[zz,:,ii,2]/float(amount)), linestyle="None", color="red")
        
		#plt.show()
		
		
		#Plot light collection efficiency and position resolution of all events as a scatter plot vs. the true radius 
		#fig = plt.figure()
		#plt.xlabel('Radius [cm]')
		#plt.ylabel('Light Collection Efficiency')
		#plt.axis([-100, max_rad*1.1/10, 0, 1.0])
		#for zz, amount in enumerate(n_ph_sim):
			#for ii in range(n_pos+1):
				#for kk in range(len(recon[zz,:,ii,2])): 
					#plt.scatter(recon[zz,0,ii,0],recon[zz,kk,ii,2]/float(amount), color="blue")
		#plt.show()
		
		#fig = plt.figure()
		#plt.xlabel('Radius [cm]')
		#plt.ylabel('Position Resolution [mm]')
		#plt.axis([-100, max_rad*1.1/10, 0, 400])
		#for zz, amount in enumerate(n_ph_sim):
			#for ii in range(n_pos+1):
				#distance = np.sqrt(recon[zz,:,ii,3]*recon[zz,:,ii,3] + recon[zz,:,ii,4]*recon[zz,:,ii,4] + recon[zz,:,ii,5]*recon[zz,:,ii,5])
				#for kk in range(len(distance)):
					#plt.scatter(recon[zz,0,ii,0], distance[kk], color="blue")	
		#plt.show()
		
        
    def radius_equal_vol(steps = 11, max_rad = 6000):
		max_vol = pow(max_rad, 3)*4/3*math.pi
		rads = [math.pow(3.0/4.0*max_vol/steps/math.pi*ii, 1/3.0) for ii in range(steps)]
		return rads 

    def set_style():
        # Set matplotlib style
        #rcParams['lines.linewidth'] = 2
        rcParams['lines.markersize'] = 4
        rcParams['font.size'] = 16.0
        rcParams['figure.figsize'] = (12, 9)
       
    def get_eff_from_root(filename, n_ph_sim, repetition, n_pos):
		f = ROOT.TFile.Open(rootdir+filename+".root")
		t = f.Get("data")  
		recon = np.zeros((len(n_ph_sim), repetition, n_pos+1, 6)) 

		for ii, entry in enumerate(t): 
			recon[0, entry.run, entry.pos,:] = [np.sqrt(entry.xpos_true*entry.xpos_true + entry.ypos_true*entry.ypos_true + entry.zpos_true*entry.zpos_true)/10, np.sqrt(entry.xpos*entry.xpos + entry.ypos*entry.ypos + entry.zpos*entry.zpos)/10, entry.photon_true, np.abs(entry.xpos_true - entry.xpos), np.abs(entry.ypos_true - entry.ypos), np.abs(entry.zpos_true - entry.zpos)]
		plot_double_yaxis(recon, n_ph_sim, n_pos, max_rad=6600)



if __name__ == '__main__':
    print "Efficiency test started"
    
    design = ['cfJiani3_2', 'cfJiani3_test2', 'cfJiani3_4', 'cfSam1_1', 'cfJiani3_2']
    suffix = '_1DVariance'
  
    energy = [6600]
    repetition = 100
    n_pos = 50 
    set_style()
    
    for select in range(2,5):
		#break
		detfile = design[select]
		if(select > 1): 
			detfile += suffix
		
		print "Lens design used:	", design[select] 
		
		eff_test(design[select], detres='detresang-'+detfile+'_noreflect_100million.root', detbins=10, sig_pos=0.01, n_ph_sim=energy, repetition=repetition, max_rad=6600, n_pos=n_pos, loc1=(0,0,0), sig_cone=0.01, lens_dia=None, n_ph=0, min_tracks=0.1, chiC=1.5, temps=[256, 0.25], tol=0.1, debug=False)
    
    filename = "cfJiani3_4"+"_rep-"+str(repetition)+"_npos-"+str(n_pos)
    #get_eff_from_root(filename=filename , n_ph_sim=energy, repetition=repetition, n_pos=n_pos)
    
    print "Simulation done."
