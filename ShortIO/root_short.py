import os, os.path
import shutil
import numpy as np
import chroma.event as event
from chroma.tools import count_nonzero
from chroma.rootimport import ROOT
# Copied from root.py; for writing shortened versions of events, with only photon positions

# Check if we have already imported the ROOT class due to a user's
# rootlogon.C script
if not hasattr(ROOT, 'Vertex') or not hasattr(ROOT, 'Channel'): #May have to change this?
    # Create .chroma directory if it doesn't exist
    chroma_dir = os.path.expanduser('~/.chroma')
    if not os.path.isdir(chroma_dir):
        if os.path.exists(chroma_dir):
            raise Exception('$HOME/.chroma file exists where directory should be')
        else:
            os.mkdir(chroma_dir)
    # Check if latest ROOT file is present
    package_root_C = os.path.join(os.path.dirname(__file__), 'root_short.C') #Using updated name; may be incorrect
    home_root_C = os.path.join(chroma_dir, 'root_short.C') #This is in chroma_dir; probably leave unchanged
    if not os.path.exists(home_root_C) or \
            os.stat(package_root_C).st_mtime > os.stat(home_root_C).st_mtime:
        shutil.copy2(src=package_root_C, dst=home_root_C)
    # ACLiC problem with ROOT
    # see http://root.cern.ch/phpBB3/viewtopic.php?f=3&t=14280&start=15
    ROOT.gSystem.Load('libCint')
    # Import this C file for access to data structure
    ROOT.gROOT.ProcessLine('.L '+home_root_C+'+')


# def tvector3_to_ndarray(vec):
    # '''Convert a ROOT.TVector3 into a numpy np.float32 array'''
    # return np.array((vec.X(), vec.Y(), vec.Z()), dtype=np.float32)

def make_photon_with_arrays(size):
    '''Returns a new chroma.event.Photons object for `size` number of
    photons with empty arrays set for all the photon attributes.'''
    return event.Photons(pos=np.empty((size,3), dtype=np.float32),
                         dir=np.empty((size,3), dtype=np.float32),
                         pol=np.empty((size,3), dtype=np.float32),
                         wavelengths=np.empty(size, dtype=np.float32),
                         t=np.empty(size, dtype=np.float32),
                         flags=np.empty(size, dtype=np.uint32),
                         last_hit_triangles=np.empty(size, dtype=np.int32))

# def root_vertex_to_python_vertex(vertex):
    # "Returns a chroma.event.Vertex object from a root Vertex object."
    # return event.Vertex(str(vertex.particle_name),
                        # pos=tvector3_to_ndarray(vertex.pos),
                        # dir=tvector3_to_ndarray(vertex.dir),
                        # ke=vertex.ke,
                        # t0=vertex.t0,
                        # pol=tvector3_to_ndarray(vertex.pol))
						
def root_event_to_python_event(ev):
    '''Returns a new chroma.event.Event object created from the
    contents of the ROOT event `ev`.'''
    pyev = event.Event(ev.id)

    # photon begin
    if ev.photons_beg.size() > 0:
        photons = make_photon_with_arrays(ev.photons_beg.size())
        ROOT.get_photons(ev.photons_beg,
                         photons.pos.ravel(),
                         photons.dir.ravel(),
                         photons.pol.ravel(),
                         photons.wavelengths,
                         photons.t,
                         photons.last_hit_triangles,
                         photons.flags)
        pyev.photons_beg = photons

    # photon end
    if ev.photons_end.size() > 0:
        photons = make_photon_with_arrays(ev.photons_end.size())
        ROOT.get_photons(ev.photons_end,
                         photons.pos.ravel(),
                         photons.dir.ravel(),
                         photons.pol.ravel(),
                         photons.wavelengths,
                         photons.t,
                         photons.last_hit_triangles,
                         photons.flags)
        pyev.photons_end = photons

    return pyev
	
def root_PMT_pdf_to_numpy_array(pdf):
    '''Returns a tuple of (pmt_bin_ind, 3D numpy array) created from the
    contents of the ROOT PMT_pdf `pdf`.'''
    
    np_pdf = np.array(pdf.counts)
    np_pdf = np.reshape(np_pdf,(pdf.detector_bins_x,pdf.detector_bins_y,pdf.detector_bins_z))

    return pdf.pmt_bin_ind, np_pdf
    
def root_PMT_angles_to_numpy_array(pmt_angles):
    '''Returns a tuple of (pmt_bin_ind, nX x nY x nZ x 3 numpy array) created from the
    contents of the ROOT PMT_angles `pmt_angles`.'''
    
    det_bins = pmt_angles.detector_bins_x*pmt_angles.detector_bins_y*pmt_angles.detector_bins_z
    ang_out = np.empty((det_bins,3), dtype=np.float32)
    ROOT.get_angles(pmt_angles.angles, ang_out.ravel())
    #print ang_out
    #print np.shape(ang_out)
    #np_ang = np.reshape(ang_out,(pmt_angles.detector_bins_x,pmt_angles.detector_bins_y,pmt_angles.detector_bins_z,3))
    #print np.shape(np_ang)
    #print np_ang[0,0,0]

    return pmt_angles.pmt_bin_ind, ang_out
    
def root_PMT_Gauss_angle_to_tuple(angle):
    '''Returns a tuple of (pmt_bin_ind, 1x3 array mean, float sigma) created from the
    contents of the ROOT Gauss_angle `angle`.'''

    mean = np.empty((1,3), dtype=np.float32)
    sigma = np.zeros(1, dtype=np.float32)
    ROOT.get_Gauss_angle(angle, mean.ravel(), sigma)
    return angle.pmt_bin_ind, mean, sigma[0]
    
class ShortRootReader(object):
    '''Reader of Chroma events from a ROOT file.  This class can be used to 
    navigate up and down the file linearly or in a random access fashion.
    All returned events are instances of the chroma.event.Event class.

    It implements the iterator protocol, so you can do

       for ev in RootReader('electron.root'):
           # process event here
    '''

    def __init__(self, filename):
        '''Open ROOT file named `filename` containing TTree `T`.'''
        self.f = ROOT.TFile(filename)
        self.T = self.f.T
        self.i = -1
        
    def __len__(self):
        '''Returns number of events in this file.'''
        return self.T.GetEntries()

    def __iter__(self):
        for i in xrange(self.T.GetEntries()):
            self.T.GetEntry(i)
            yield root_event_to_python_event(self.T.ev)

    def next(self):
        '''Return the next event in the file. Raises StopIteration
        when you get to the end.'''
        if self.i + 1 >= len(self):
            raise StopIteration

        self.i += 1
        self.T.GetEntry(self.i)
        return root_event_to_python_event(self.T.ev)

    def prev(self):
        '''Return the next event in the file. Raises StopIteration if
        that would go past the beginning.'''
        if self.i <= 0:
            self.i = -1
            raise StopIteration

        self.i -= 1
        self.T.GetEntry(self.i)
        return root_event_to_python_event(self.T.ev)

    def current(self):
        '''Return the current event in the file.'''
        self.T.GetEntry(self.i) # in case we were iterated over elsewhere
        return root_event_to_python_event(self.T.ev)

    def jump_to(self, index):
        '''Return the event at `index`.  Updates current location.'''
        if index < 0 or index >= len(self):
            raise IndexError
        
        self.i = index

        self.T.GetEntry(self.i)
        return root_event_to_python_event(self.T.ev)

    def index(self):
        '''Return the current event index'''
        return self.i

class ShortRootWriter(object):
    def __init__(self, filename):
        self.filename = filename
        self.file = ROOT.TFile(filename, 'RECREATE')

        self.T = ROOT.TTree('T', 'Chroma events')
        self.ev = ROOT.Event_short()
        self.T.Branch('ev', self.ev)

    def write_event(self, pyev):
        "Write an event.Event object to the ROOT tree as a ROOT.Event object."
        self.ev.id = pyev.id

        if pyev.photons_beg is not None:
            photons = pyev.photons_beg
            ROOT.fill_photons(self.ev.photons_beg,
                              len(photons.pos),
                              photons.pos.ravel(),
                              photons.flags)

        if pyev.photons_end is not None:
            photons = pyev.photons_end
            ROOT.fill_photons(self.ev.photons_end,
                              len(photons.pos),
                              photons.pos.ravel(),
                              photons.flags)

        self.T.Fill()

    def close(self):
        self.T.Write()
        self.file.Close()
		
class PDFRootWriter(object):
	#Writes 3D numpy arrays, corresponding to detector PDFs, to a ROOT file as ROOT.PMT_pdf objects
    def __init__(self, filename):
        self.filename = filename
        self.file = ROOT.TFile(filename, 'RECREATE')

        self.T = ROOT.TTree('T', 'PDFs')
        self.pdf = ROOT.PMT_pdf()
        self.T.Branch('pdf', self.pdf)

    def write_event(self, pdf, pmt_bin_ind):
        "Write 3D numpy array (PDF) to a ROOT.PMT_pdf object."
        if np.shape(pdf) == (0,):
            return
        pdf_shape = np.shape(pdf)
        if len(pdf_shape) != 3:
            print "Error: array to write must be 3-dimensional."
            return
        self.pdf.pmt_bin_ind = pmt_bin_ind
        self.pdf.detector_bins_x = pdf_shape[0]
        self.pdf.detector_bins_y = pdf_shape[1]
        self.pdf.detector_bins_z = pdf_shape[2]
        
        #Fill ROOT.PMT_pdf object by flattening 3D array to 1D w/ ravel; flattens along inner dimensions first
        ROOT.fill_pdf(self.pdf, np.size(pdf), pdf.ravel()) 
        self.T.Fill()

    def close(self):
        self.T.Write()
        self.file.Close()

class PDFRootReader(object):
    '''Reader of detector PDFs from a ROOT file. 

    It implements the iterator protocol, so you can do

       for bin_ind, pdf in RootReader('filename.root'):
           # process pdf here
    '''

    def __init__(self, filename):
        '''Open ROOT file named `filename` containing TTree `T`.'''
        self.f = ROOT.TFile(filename)
        self.T = self.f.T
        self.i = -1
        
    def __len__(self):
        '''Returns number of pdfs in this file.'''
        return self.T.GetEntries()

    def __iter__(self):
        for i in xrange(self.T.GetEntries()):
            self.T.GetEntry(i)
            yield root_PMT_pdf_to_numpy_array(self.T.pdf)

    def next(self):
        '''Return the next pdf in the file. Raises StopIteration
        when you get to the end.'''
        if self.i + 1 >= len(self):
            raise StopIteration

        self.i += 1
        self.T.GetEntry(self.i)
        return root_PMT_pdf_to_numpy_array(self.T.pdf)

    def prev(self):
        '''Return the previous pdf in the file. Raises StopIteration if
        that would go past the beginning.'''
        if self.i <= 0:
            self.i = -1
            raise StopIteration

        self.i -= 1
        self.T.GetEntry(self.i)
        return root_PMT_pdf_to_numpy_array(self.T.pdf)

    def current(self):
        '''Return the current pdf in the file.'''
        self.T.GetEntry(self.i) # in case we were iterated over elsewhere
        return root_PMT_pdf_to_numpy_array(self.T.pdf)

    def jump_to(self, index):
        '''Return the event at `index`.  Updates current location.'''
        if index < 0 or index >= len(self):
            raise IndexError
        
        self.i = index

        self.T.GetEntry(self.i)
        return root_PMT_pdf_to_numpy_array(self.T.pdf)

    def index(self):
        '''Return the current event index'''
        return self.i

class AngleRootWriter(object):
	#Writes numpy arrays, corresponding to detected angles, to a ROOT file as ROOT.PMT_angles objects
    def __init__(self, filename):
        self.filename = filename
        self.file = ROOT.TFile(filename, 'RECREATE')

        self.T = ROOT.TTree('T', 'Angles')
        self.angles = ROOT.PMT_angles()
        self.T.Branch('angles', self.angles)

    def write_PMT(self, angles, pmt_bin_ind, nx, ny, nz):
        #Write nbins x 3 numpy array (angles; one 3D direction per detector bin) to a ROOT.PMT_angles object.
        if np.shape(angles) == (0,):
            return
        angles_shape = np.shape(angles)
        if angles_shape[0] != nx*ny*nz:
            print "Error: length of angles array must equal nxbins*nybins*nzbins."
            return
        if angles_shape[1] != 3:
            print "Error: each entry must have three coordinates."
            return
        self.angles.pmt_bin_ind = pmt_bin_ind
        self.angles.detector_bins_x = nx
        self.angles.detector_bins_y = ny
        self.angles.detector_bins_z = nz
        
        #Fill ROOT.PMT_angles object by flattening 3D array to 1D w/ ravel; flattens along inner dimensions first
        ROOT.fill_angles(self.angles, angles_shape[0], angles.ravel()) 
        self.T.Fill()

    def close(self):
        self.T.Write()
        self.file.Close()
        
class AngleRootReader(object):
    '''Reader of pmt angle lists from a ROOT file. 

    It implements the iterator protocol, so you can do

       for bin_ind, angles in RootReader('filename.root'):
           # process angles here
    '''

    def __init__(self, filename):
        '''Open ROOT file named `filename` containing TTree `T`.'''
        self.f = ROOT.TFile(filename)
        self.T = self.f.T
        self.i = -1
        
    def __len__(self):
        '''Returns number of pmt angle lists in this file.'''
        return self.T.GetEntries()

    def __iter__(self):
        for i in xrange(self.T.GetEntries()):
            self.T.GetEntry(i)
            yield root_PMT_angles_to_numpy_array(self.T.angles)

    def next(self):
        '''Return the next angle list in the file. Raises StopIteration
        when you get to the end.'''
        if self.i + 1 >= len(self):
            raise StopIteration

        self.i += 1
        self.T.GetEntry(self.i)
        return root_PMT_angles_to_numpy_array(self.T.angles)

    def prev(self):
        '''Return the previous angle list in the file. Raises StopIteration if
        that would go past the beginning.'''
        if self.i <= 0:
            self.i = -1
            raise StopIteration

        self.i -= 1
        self.T.GetEntry(self.i)
        return root_PMT_angles_to_numpy_array(self.T.angles)

    def current(self):
        '''Return the current angle list in the file.'''
        self.T.GetEntry(self.i) # in case we were iterated over elsewhere
        return root_PMT_angles_to_numpy_array(self.T.angles)

    def jump_to(self, index):
        '''Return the angle list at `index`.  Updates current location.'''
        if index < 0 or index >= len(self):
            raise IndexError
        
        self.i = index

        self.T.GetEntry(self.i)
        return root_PMT_angles_to_numpy_array(self.T.angles)

    def index(self):
        '''Return the current angle list index'''
        return self.i

class GaussAngleRootWriter(object):
	#Writes numpy arrays, corresponding to mean angle and sigmas, to a ROOT file as ROOT.Gauss_angle objects
    def __init__(self, filename):
        self.filename = filename
        self.file = ROOT.TFile(filename, 'RECREATE')

        self.T = ROOT.TTree('T', 'Angles')
        self.angle = ROOT.Gauss_angle()
        self.T.Branch('angles', self.angle)

    def write_PMT(self, mean, sigma, pmt_bin_ind):
        #Write a 1x3 numpy array (mean) and float sigma to a ROOT.Gauss_angle object.
        mean_shape = np.shape(mean)
        if mean_shape[0] != 3:
            print "Error: mean must have three coordinates."
            return
        self.angle.pmt_bin_ind = pmt_bin_ind
        
        #Fill ROOT.Gauss_angle object by flattening 3D array to 1D w/ ravel; flattens along inner dimensions first
        ROOT.fill_Gauss_angle(self.angle, mean, sigma) 
        self.T.Fill()

    def close(self):
        self.T.Write()
        self.file.Close()
        
class GaussAngleRootReader(object):
    '''Reader of pmt mean angle and sigma from a ROOT file. 

    It implements the iterator protocol, so you can do

       for bin_ind, mean, sigma in GaussAngleRootReader('filename.root'):
           # process angle here
    '''

    def __init__(self, filename):
        '''Open ROOT file named `filename` containing TTree `T`.'''
        self.f = ROOT.TFile(filename)
        self.T = self.f.T
        self.i = -1
        
    def __len__(self):
        '''Returns number of pmt angle lists in this file.'''
        return self.T.GetEntries()

    def __iter__(self):
        for i in xrange(self.T.GetEntries()):
            self.T.GetEntry(i)
            yield root_PMT_Gauss_angle_to_tuple(self.T.angles)

    def next(self):
        '''Return the next angle list in the file. Raises StopIteration
        when you get to the end.'''
        if self.i + 1 >= len(self):
            raise StopIteration

        self.i += 1
        self.T.GetEntry(self.i)
        return root_PMT_Gauss_angle_to_tuple(self.T.angles)

    def prev(self):
        '''Return the previous angle list in the file. Raises StopIteration if
        that would go past the beginning.'''
        if self.i <= 0:
            self.i = -1
            raise StopIteration

        self.i -= 1
        self.T.GetEntry(self.i)
        return root_PMT_Gauss_angle_to_tuple(self.T.angles)

    def current(self):
        '''Return the current angle list in the file.'''
        self.T.GetEntry(self.i) # in case we were iterated over elsewhere
        return root_PMT_Gauss_angle_to_tuple(self.T.angles)

    def jump_to(self, index):
        '''Return the angle list at `index`.  Updates current location.'''
        if index < 0 or index >= len(self):
            raise IndexError
        
        self.i = index

        self.T.GetEntry(self.i)
        return root_PMT_Gauss_angle_to_tuple(self.T.angles)

    def index(self):
        '''Return the current angle list index'''
        return self.i
