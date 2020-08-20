# pylint: disable=
import numpy as np


def parse_bool_string(string): # Interpret string as true or false
    """Convert string to boolean value."""
    return (string[0].upper() == 'T') or (string.upper() == 'ON') or (string[0].upper() == 'Y')

def to_pmol(number):
    """Convert a number to [pmol] unit."""
    return number*1e12/6.022e23

class IntegrateCurrent(object): # pylint: disable=useless-object-inheritance
    """Integrate current in an 'omicron' deposition measurement to get total charge and coverage.

    Parameters
    ----------
    data : ndarray
        time as first column in `data`
        current as second column in `data`
    parameter_string : string
        semicolon-separated 'key=value" pairs:

        MODEL -- model to calculate coverage from (NP/SA)
        SA_DENSITY -- "SA" single atom density (unit: cm**-2)
        PARTICLE_DIAMETER -- "NP" diameter of nanoparticles (unit: nm)
        APERTURE_DIAMETER -- "NP/SA" diameter of deposition aperture/area (unit: mm)
        TARGET -- target coverage used for time estimate (unit: percent, default: 0)
        TIME -- time interval to integrate. Leave empty for full interval (unit: s)
        PLOT -- determine whether a figure should be produced (True/False)
        DEBUG -- plot a figure to help determine `SENSITIVITY_X` (True/False)
    """

    def __init__(self, parameter_string, data, plot=True):
        """Assign parameters as attributes."""
        string = parameter_string.strip(';').split(';')
        self.debugging = False
        self.model, self.target, self.time = None, None, list()
        if plot:
            import matplotlib.pyplot as plt
            self.plt = plt
            self.plot = plot
        for item in string:
            param, value = item.split('=')
            if param == 'LEAK_CURRENT':
                self.leak_current = float(value)
            elif param == 'PARTICLE_DIAMETER':
                radius_particle = float(value)/2.*1e-9
                self.area_particle = np.pi * ((radius_particle)**2)
            elif param == 'APERTURE_DIAMETER':
                radius_aperture = float(value)/2.*1e-3
                self.area_aperture = np.pi * ((radius_aperture)**2)
            elif param == 'DEBUG':
                self.debugging = parse_bool_string(value)
            elif param == 'MODEL':
                if value in ['NP', 'SA']:
                    self.model = value
                else:
                    print('MODEL must have either "NP" or "SA"')
            elif param == 'SA_DENSITY':
                self.sa_density = float(value)
            elif param == 'TARGET':
                self.target = [float(value)]
                if not self.target[0] > 0:
                    self.target = np.array([5, 10, 15, 20, 25, 30, 40, 50, 75, 100, 150, 200, 300])
            elif param == 'TIME':
                value = value.strip('[]')
                if value:
                    self.time = [float(val) for val in value.split(',')]
            else:
                print('par/val pair ({0}/{1}) not recognized'.format(param, value))

        # Store data
        self.data = data
        self.dep_rate = None
        self.present_coverage = None

    def convert_coverage_to_number(self, coverage):
        """Convert target coverage from percent to number of particles."""
        if self.model is None:
            print('Model not chosen!')
            number = None
        elif self.model == 'SA':
            print('Single atoms model not implemented yet!')
            number = None
        elif self.model == 'NP':
            number = coverage/100.*self.area_aperture/self.area_particle
        return number

    def convert_number_to_coverage(self, number):
        """Convert coverage from number of particles to percent."""
        if self.model is None:
            print('Model not chosen!')
            coverage = None
        elif self.model == 'SA':
            print('Single atoms model not implemented yet!')
            coverage = None
        elif self.model == 'NP':
            coverage = number*100/self.area_aperture*self.area_particle
        return coverage

    def integrate(self):
        """Integrate the current and return the number of particles."""


        # Set leak current from string
        leak_current = self.leak_current

        if self.time:
            self.data = self.data[np.where(self.data[:, 0] >= self.time[0])]
            self.data = self.data[np.where(self.data[:, 0] <= self.time[1])]

        # Integrate deposition current
        e = 1.602e-19 # pylint: disable=invalid-name
        net_current = np.abs(self.data[:, 1] + leak_current)
        integral = np.sum(net_current[1:] * np.diff(self.data[:, 0]))/e
        print(integral)
        dep_rate = net_current[np.where(net_current > 1e-13)][-100:]
        dep_rate = np.average(dep_rate)/e

        # Estimate time to next coverage step
        present_coverage = self.convert_number_to_coverage(integral)
        for coverage in self.target:
            if coverage >= present_coverage:
                target_coverage = coverage
                break
            else:
                target_coverage = self.target[-1]
        target_number = self.convert_coverage_to_number(target_coverage)

        # If specific target chosen or over 300 %, else...
        if target_number < integral:
            msg = 'Target coverage ({0} %) already exceeded: {1} %.'
            print(msg.format(target_coverage, present_coverage))
            print('Number of clusters: {0} pmol.'.format(to_pmol(integral)))
        else:
            msg = 'Total charge deposited: {} pmol.\n'.format(to_pmol(integral))
            msg += 'Present coverage: {} %\n'.format(present_coverage)
            msg += 'Time until {} % coverage: {} hr {} min {} sec'
            remaining = target_number - integral
            time_left = remaining/dep_rate
            time_hr = int(time_left/3600)
            time_min = int((time_left - time_hr*3600)/60)
            time_sec = int(time_left - time_hr*3600 - time_min*60)
            print(msg.format(target_coverage, time_hr, time_min, time_sec))


################################################################
### MAIN ###
################################################################
if __name__ == '__main__':

    #import rcparam
    from cinfdata import Cinfdata
    db = Cinfdata('stm312', use_caching=False) # pylint: disable=invalid-name
    ID = 13602
    STRING = '\
TARGET=10.0;\
MODEL=NP;\
SA_DENSITY=1;\
LEAK_CURRENT=1e-12;\
PARTICLE_DIAMETER=1.3;\
APERTURE_DIAMETER=7;\
TIME=[0,9200]'
    try:
        SESSION = IntegrateCurrent(STRING, db.get_data(ID))
        SESSION.integrate()
        if SESSION.plot:
            SESSION.plt.show()
    except:
        print('***\nSomething is wrong: Check input parameters or try debugging mode!!\n***')
        SESSION.plt.show()
        raise
    # for 9x9 raster pattern: ap_dia ~ 12.4 mm (120.8 mm2 ~ 11x11 mm)
    # for 5x5 raster pattern: ap_dia ~ 6.7 mm (35.3 mm2)
    #                 [*** Based on simul. 12/12-18 use ap_dia ~ 9.0mm]
    # for localized_Z pattern: ap_dia ~ 4.81 mm (18.2 mm2 ~ 5.2x3.5 mm)
