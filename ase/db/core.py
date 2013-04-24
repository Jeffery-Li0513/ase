import os
from time import time

from ase.atoms import Atoms
from ase.parallel import world
from ase.utils import Lock, OpenLock
from ase.data import atomic_numbers
from ase.calculators.singlepoint import SinglePointCalculator


T0 = 1366375643.236751


def connect(name, type='use_filename_extension', use_lock_file=False):
    if type == 'use_filename_extension':
        if name is None:
            type = None
        else:
            type = os.path.splitext(name)[1][1:]

    if type is None:
        return NoDatabase()

    if type == 'json':
        from ase.db.json import JSONDatabase as DB
    elif type == 'sqlite3':
        from ase.db.sqlite3 import SQLite3Database as DB
    else:
        assert 0
    return DB(name, use_lock_file=use_lock_file)


class FancyDict(dict):
    def __getattr__(self, key):
        if key not in self:
            return dict.__getattr__(self, key)
        value = self[key]
        if isinstance(value, dict):
            return FancyDict(value)
        return value


class NoDatabase:
    def __init__(self, filename=None, use_lock_file=False):
        self.filename = filename
        if use_lock_file:
            self.lock = Lock(filename + '.lock')
        else:
            self.lock = OpenLock()

        self.timestamp = None  # timestamp form last write

    def write(self, id, atoms, keywords=[], key_value_pairs={}, data={},
              timestamp=None, replace=True):
        if world.rank > 0:
            return

        if id is None:
            id = self.create_random_id(atoms)

        if timestamp is None:
            timestamp = (time() - T0) / 86400
        self.timestamp = timestamp

        #with self.lock: PY24
        #    self._write(id, atoms, data, replace)
        self.lock.acquire()
        try:
            self._write(id, atoms, keywords, key_value_pairs, data, replace)
        finally:
            self.lock.release()

    def _write(self, id, atoms, keywords, key_value_pairs, data, replace):
        pass

    def collect_data(self, atoms):
        dct = {'timestamp': self.timestamp,
               'username': os.getenv('USER')}
        if atoms is None:
            return dct
        dct.update(atoms2dict(atoms))
        if atoms.calc is not None:
            dct['calculator_name'] = atoms.calc.name.lower()
            dct['calculator_parameters'] = atoms.calc.todict()
            if len(atoms.calc.check_state(atoms)) == 0:
                dct['results'] = atoms.calc.results
            else:
                dct['results'] = {}
        return dct

    def get_dict(self, id, fancy=True):
        dct = self._get_dict(id)
        if fancy:
            dct = FancyDict(dct)
        return dct

    def get_atoms(self, id=0, attach_calculator=False,
                  add_additional_information=False):
        dct = self.get_dict(id, fancy=False)
        atoms = dict2atoms(dct, attach_calculator)
        if add_additional_information:
            atoms.info = {'id': id,
                          'keywords': dct['keywords'],
                          'key_value_pairs': dct['key_value_pairs'],
                          'data': dct['data']}
        return atoms

    def __getitem__(self, index):
        if index == slice(None, None, None):
            return [self[0]]
        return self.get_atoms(index)

    def iselect(self, *expressions, **kwargs):
        username = kwargs.pop('username', None)  # PY24
        charge = kwargs.pop('charge', None)
        calculator = kwargs.pop('calculator', None)
        filter = kwargs.pop('filter', None)
        if expressions:
            expressions = ','.join(expressions).split(',')
        keywords = []
        comparisons = []
        for expression in expressions:
            if not isinstance(expression, str):
                comparisons.append(expression)
                continue
            if expression.count('<') == 2:
                value, expression = expression.split('<', 1)
                if expression[0] == '=':
                    op = '>='
                    expression = expression[1:]
                else:
                    op = '>'
                key = expression.split('<', 1)[0]
                comparisons.append((key, op, value))
            for op in ['<=', '>=', '<', '>', '=']:
                if op in expression:
                    break
            else:
                keywords.append(expression)
                continue
            key, value = expression.split(op)
            comparisons.append((key, op, value))
        cmps = []
        for key, op, value in comparisons:
            if key == 'age':
                key = 'timestamp'
                op = {'<': '>', '<=': '>=', '>=': '<=', '>': '<'}.get(op, op)
                value = (time() - T0) / 86400 - time_string_to_float(value)
            elif key == 'calculator':
                key = 'calculator_name'
            elif key in atomic_numbers:
                key = atomic_numbers[key]
                value = int(value)
            else:
                try:
                    value = float(value)
                except ValueError:
                    assert op == '='
            print (key, op, value)
            cmps.append((key, op, value))
        if username is not None:
            cmps.append(('username', '=', username))
        if charge is not None:
            cmps.append(('charge', '=', charge))
        if calculator is not None:
            cmps.append(('claculator_name', '=', calculator))
        for symbol, n in kwargs.items():
            assert isinstance(n, int)
            Z = atomic_numbers[symbol]
            cmps.append((Z, op, n))
        for dct in self._iselect(keywords, cmps):
            if filter is None or filter(dct):
                yield dct


def atoms2dict(atoms):
    data = {
        'numbers': atoms.numbers,
        'pbc': atoms.pbc,
        'cell': atoms.cell,
        'positions': atoms.positions}
    if atoms.has('magmoms'):
        data['magmoms'] = atoms.get_initial_magnetic_moments()
    if atoms.has('charges'):
        data['charges'] = atoms.get_initial_charges()
    if atoms.has('masses'):
        data['masses'] = atoms.get_masses()
    if atoms.has('tags'):
        data['tags'] = atoms.get_tags()
    if atoms.has('momenta'):
        data['momenta'] = atoms.get_momenta()
    if atoms.constraints:
        data['constraints'] = [c.todict() for c in atoms.constraints]
    return data


def dict2atoms(dct, attach_calculator=False):
    constraint_dicts = dct.get('constraints')
    if constraint_dicts:
        constraints = []
        for c in constraint_dicts:
            assert c.pop('name') == 'ase.constraints.FixAtoms'
            constraints.append(FixAtoms(**c))
    else:
        constraints = None

    atoms = Atoms(dct['numbers'],
                  dct['positions'],
                  cell=dct['cell'],
                  pbc=dct['pbc'],
                  magmoms=dct.get('magmoms'),
                  charges=dct.get('charges'),
                  tags=dct.get('tags'),
                  masses=dct.get('masses'),
                  momenta=dct.get('momenta'),
                  constraint=constraints)

    results = dct.get('results')
    if attach_calculator:
        atoms.calc = get_calculator(dct['calculator_name'])(
            **dct['calculator_parameters'])
    elif results:
        atoms.calc = SinglePointCalculator(atoms, **results)

    return atoms


def time_string_to_float(s):
    if isinstance(s, (float, int)):
        return s
    s = s.replace(' ', '')
    if '+' in s:
        return sum(time_string_to_float(x) for x in s.split('+'))
    if s[-2].isalpha() and s[-1] == 's':
        s = s[:-1]
    i = 1
    while s[i].isdigit():
        i += 1
    return {'s': 1, 'second': 1,
            'm': 60, 'minute': 60,
            'h': 3600, 'hour': 3600,
            'd': 86400, 'day': 86400,
            'w': 604800, 'week': 604800,
            'M': 2592000, 'month': 2592000,
            'y': 31622400, 'year': 31622400}[s[i:]] * int(s[:i]) / 86400.0
