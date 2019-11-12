
import sys
from pathlib import Path
sys.path.append(".")

import pytest

from corems.mass_spectra.output.export import MassSpectraExport
from corems.mass_spectrum.output.export import MassSpecExport
from corems.mass_spectrum.input.massList import ReadCoremsMasslist
from corems.mass_spectra.input.boosterHDF5 import ReadHDF_BoosterMassSpectra

def import_corems_mass_list():

    file_location = Path.cwd() / "tests/tests_data/" / "ESI_NEG_SRFA_COREMS.csv"
    
    #polariy need to be set or read from the file
    
    #load any type of mass list file, change the delimeter to read another type of file, i.e : "," for csv, "\t" for tabulated mass list, etc
    mass_list_reader = ReadCoremsMasslist(file_location, delimiter=",")

    mass_spectrum = mass_list_reader.get_mass_spectrum()

    return mass_spectrum

def import_booster_mass_spectra_hdf():

    file_path = Path.cwd() / "tests/tests_data/" / "ESFA_100k_9767-13548_chB.A_re_pc_CoAddAll_mFT.h5"
    
    if file_path.exists:
        #polariy need to be set or read from the file
        booster_reader = ReadHDF_BoosterMassSpectra(file_path)

        booster_reader.start()
        booster_reader.join()
    
    return booster_reader.get_lcms_obj()


def test_export_mass_spectra():

    mass_spectra = import_booster_mass_spectra_hdf()

    exportMS= MassSpectraExport('NEG_ESI_SRFA_CoreMS', mass_spectra)

    exportMS.to_pandas()
    exportMS.to_excel()
    exportMS.to_csv()
    exportMS.to_hdf()


def test_export_mass_spectrum():

    mass_spectrum = import_corems_mass_list()

    exportMS= MassSpecExport('NEG_ESI_SRFA_CoreMS', mass_spectrum)

    exportMS.to_pandas()
    exportMS.to_excel()
    exportMS.to_csv()
    exportMS.to_hdf()

if __name__ == "__main__":
                        
    #test_export_mass_spectra()
    test_export_mass_spectrum()
    