__author__ = "Yuri E. Corilo"
__date__ = "Jul 31, 2019"

from copy import deepcopy
from threading import Thread
from numpy import average, std
from enviroms.molecular_id.calc.ClusterFilter import ClusteringFilter
from enviroms.molecular_id.calc.MolecularFormulaSearch import SearchMolecularFormulas
from enviroms.molecular_id.factory.MolecularFormulaFactory import MolecularFormula
from isort import settings


class FindOxygenPeaks(Thread):
    
    '''
        Class to walk 14Da units over oxygen space for negative ion mass spectrum of natural organic matter
        Returns a list of MSPeak class cotaining the possibles Molecular Formula class objects.  
        
        Parameters
        ----------
        mass_spectrum_obj : MassSpec class
            This is where we store MassSpec class obj,   
        
        lookupTableSettings:  MoleculaLookupTableSettings class
            This is where we store MoleculaLookupTableSettings class obj
        
        min_O , max_O : int
            minum and maxium of oxigen to allow the software to look for
            it will override the settings at lookupTableSettings.usedAtoms
            default min = 1, max = 30

        Attributes
        ----------
        mass_spectrum_obj : MassSpec class
            This is where we store MassSpec class obj,   
        lookupTableSettings:  MoleculaLookupTableSettings class
            This is where we store MoleculaLookupTableSettings class obj
        
        Methods
        ----------
            run()    
                will be called when the instaciated class method start is called
            get_list_found_peaks()
                returns a list of MSpeaks classes cotaining all the MolecularFormula canditates inside the MSPeak
                for more details of the structure see MSPeak class and MolecularFormula class    
            set_mass_spec_indexes_by_found_peaks()
                set the mass spectrum to interate over only the selected indexes
    '''
    def __init__(self, mass_spectrum_obj, lookupTableSettings, min_O = 1, max_O = 30) :
        
        Thread.__init__(self)
        
        self.mass_spectrum_obj = mass_spectrum_obj
        self.lookupTableSettings = lookupTableSettings
        self.min_0 = min_O
        self.max_O = max_O
        

    def run(self):
        
        usedAtoms = deepcopy(self.lookupTableSettings.usedAtoms)
        
        #resets the used atoms to look only for oxygened organic compounds
        self.lookupTableSettings.usedAtoms = {'O': (self.min_0, self.max_O),
                                              'N' : (0, 0),
                                              'S' : (0, 0),
                                              'P' : (0, 0) }
        self.lookupTableSettings.usedAtoms['H'] = usedAtoms['H']
        self.lookupTableSettings.usedAtoms['C'] = usedAtoms['C']
        
        self.list_found_mspeaks = []

        kendrick_base =  {'C':1,'H':2,'O':1}   
        
        self.mass_spectrum_obj.change_kendrick_base_all_mspeaks(kendrick_base)
        
        # needs to be wrapped inside the mass_spec class
        ClusteringFilter().filter_kendrick(self.mass_spectrum_obj)
        
        molecular_formula_obj_reference = self.find_most_abundant_formula(self.mass_spectrum_obj, self.lookupTableSettings)
        
        self.list_found_mspeaks = self.find_series_mspeaks(self.mass_spectrum_obj,
                                                           molecular_formula_obj_reference, 
                                                           self.lookupTableSettings,
                                                           deltamz=14)
        
        #possible_mol_formulas_objs = self.build_database(molecular_formula_obj_reference)
        #reset indexes after done with operation that includes a filter (i.e. ClusteringFilter().filter_kendrick())
        self.mass_spectrum_obj.reset_indexes()
        self.lookupTableSettings.usedAtoms = usedAtoms

    def find_most_abundant_formula(self, mass_spectrum_obj, settings):
        '''
        find most abundant using kendrick 
        
        Returns
        ----------
        MolecularFormula class obj
            most abundant MolecularFormula with the lowest mass error
        '''
        #need to find a better way to cut off outliners
        #import matplotlib.pyplot as plt
        #plt.hist(mass_spectrum_obj.abundance_centroid, bins=100)
        #plt.show()
        
        abundances =  mass_spectrum_obj.abundance_centroid
        abun_mean = average(abundances, axis=0)
        abun_std = std(abundances, axis=0)
        
        upper_limit = abun_mean + 7* abun_std
        
        print(upper_limit, max(mass_spectrum_obj, key=lambda m: m.abundance).abundance)
        
        mspeak_most_abundant = max(mass_spectrum_obj, key=lambda m: m.abundance if m.abundance <= upper_limit else 0)

        SearchMolecularFormulas().run_worker_ms_peak(mspeak_most_abundant, mass_spectrum_obj, settings)
        
        if mspeak_most_abundant:

            return mspeak_most_abundant.molecular_formula_lowest_error 
        
        else:
        
            raise Exception("Could not find a possible molecular formula match for the most abudant peak of m/z %.5f"%mspeak_most_abundant.mz_exp )
        
        #return the first option
        #return mspeak_most_abundant[0]

    def find_most_abundant_formula_test(self, mass_spectrum_obj, settings):
        
        #this function is intended for test only. 
        # Have to sort by Kendrick to be able to select the most abundant series 
        #then select the most abundant peak inside the series
        #or have the user select the reference mspeak on the gui

        mspeak_most_abundant = mass_spectrum_obj.most_abundant_mspeak

        SearchMolecularFormulas().run_worker_ms_peak(mspeak_most_abundant, mass_spectrum_obj, settings)
        
        if mspeak_most_abundant:

            return mspeak_most_abundant.molecular_formula_lowest_error 
        else:
            raise Exception("Could not find a possible molecular formula match for the most abudant peak of m/z %.5f"%mspeak_most_abundant.mz_exp )
        #return the first option
        #return mspeak_most_abundant[0]
    
    def find_series_mspeaks(self, mass_spectrum_obj, molecular_formula_obj_reference, lookupTableSettings, deltamz=14):

        abundances =  mass_spectrum_obj.abundance_centroid
        abun_mean = average(abundances, axis=0)
        abun_std = std(abundances, axis=0)
        upper_limit = abun_mean + 7* abun_std
       

        list_most_abundant_peaks = list()

        min_mz = mass_spectrum_obj.min_mz_exp
        
        max_mz = mass_spectrum_obj.max_mz_exp
        
        initial_nominal_mass = molecular_formula_obj_reference.mz_nominal_theo
        
        mass = initial_nominal_mass
        
        nominal_masses = []
        print('min_mz', min_mz)
        print('max_mz', max_mz)
        while mass <= max_mz:
            #print "shit 1", mass, min_mz
            mass += (deltamz) 
            nominal_masses.append(mass)
        
        mass = initial_nominal_mass    
        while mass >= min_mz:
            #print "shit 1", mass, min_mz
            mass -= (deltamz) 
            nominal_masses.append(mass)
        
        nominal_masses = sorted(nominal_masses)
        
        for nominal_mass in nominal_masses:
            
            first_index, last_index = mass_spectrum_obj.get_nominal_mz_frist_last_indexes(nominal_mass)
            
            ms_peaks = mass_spectrum_obj[first_index:last_index]
            
            if ms_peaks:   
                '''    
                print (nominal_mass, first_index, 
                    last_index, 
                    mass_spectrum_obj[first_index].mz_exp,
                    mass_spectrum_obj[last_index].mz_exp
                    )
                '''
                
                mspeak_most_abundant = max(ms_peaks, key=lambda m: m.abundance if m.abundance <= upper_limit else 0)

                #mspeak_most_abundant = max(ms_peaks, key=lambda m: m.abundance)
                
                list_most_abundant_peaks.append(mspeak_most_abundant)
        
        SearchMolecularFormulas().run_worker_ms_peaks(list_most_abundant_peaks, mass_spectrum_obj, lookupTableSettings)
        
        return [mspeak for mspeak in list_most_abundant_peaks if mspeak]            
                
    
    def get_list_found_peaks(self):
        
        return sorted(self.list_found_mspeaks, key=lambda mp: mp.mz_exp)

    def set_mass_spec_indexes_by_found_peaks(self):
        
        '''
        Wanining!!!!
        set the mass spectrum to interate over only the selected indexes
        don not forget to call mass_spectrum_obj.reset_indexes after the job is done
        '''
        
        indexes = [msp.index for msp in self.list_found_mspeaks]
        self.mass_spectrum_obj.set_indexes(indexes)
        
        