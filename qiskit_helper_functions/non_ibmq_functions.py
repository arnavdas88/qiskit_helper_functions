import math, random, pickle, os, copy
from qiskit import QuantumCircuit, execute
from qiskit.providers import aer
from qiskit.circuit.classicalregister import ClassicalRegister
import qiskit.circuit.library as library
from qiskit.circuit.library import CXGate, IGate, RZGate, SXGate, XGate
from qiskit.converters import circuit_to_dag, dag_to_circuit
from qiskit.dagcircuit.dagcircuit import DAGCircuit
import numpy as np

from qiskit.providers.aer import noise
from qiskit import QuantumCircuit
from qiskit.providers.aer import AerSimulator
from qiskit.tools.visualization import plot_histogram
from qiskit.test.mock import FakeBackend, FakeTokyo, FakeVigo, FakeMelbourne, FakePoughkeepsie, FakeQasmSimulator, FakeRueschlikon, FakeTenerife

from qcg.generators import gen_supremacy, gen_hwea, gen_BV, gen_qft, gen_sycamore, gen_adder, gen_grover
from qiskit_helper_functions.conversions import dict_to_array
from qiskit_helper_functions.tket_functions import Tket

available_backend = {
    "FakeTokyo": FakeTokyo, 
    "FakeVigo": FakeVigo, 
    "FakeMelbourne": FakeMelbourne, 
    "FakePoughkeepsie": FakePoughkeepsie, 
    "FakeRueschlikon": FakeRueschlikon, 
    "FakeTenerife": FakeTenerife
}

def get_alloted_backend(backend_stack, circ):
    for device, circuits in backend_stack.items():
        if circ in circuits:
            return device
    from pprint import pprint
    pprint(backend_stack)
    print("\n\n")
    print(type(circ))
    print([ circ ])
    raise Exception(f"The circuit {[circ]} has not been alocated to any device")

def get_backend_name(backend):
    for name, device in available_backend.items():
        if device is backend:
            return name
        if backend == name:
            return name
    raise Exception(f"Backend Error: No specified backend {str(backend)} found.")


class CircuitLargerThanChip(Exception):
    pass

def check_chip_compatiblity(backend, circuit, raise_exception=True):
    if backend._configuration.n_qubits < circuit.num_qubits:
        if raise_exception:
            raise CircuitLargerThanChip(f"Circuit is larger than chip size.\nChip:{backend}\tCircuit:{circuit.num_qubits}")
        else:
            return False
    # print(f"Chip:{backend} {backend._configuration.n_qubits}\tCircuit:{circuit.num_qubits}")
    return True

def try_fakeBackend(circuit, backend, options=None, TKET = False):
    if "tket_" in str(backend):
        backend_name = get_backend_name(backend[5:])
        TKET = True
    else:
        backend_name = get_backend_name(backend)
    # print("BACKEND : ", backend_name)
    if backend_name in available_backend:
        backend = available_backend[backend_name]()
        # if ENABLE_GPU:
        #     backend.set_options(device='GPU')
        
        backend.set_options(max_parallel_shots=1024)
        # backend.set_options(max_parallel_threads=500, max_parallel_experiments=1024, max_parallel_shots=1024)
        noise_model = noise.NoiseModel.from_backend(backend)
        if isinstance(options,dict) and 'num_shots' in options:
            num_shots = options['num_shots']
        else:
            num_shots = max(1024,2**circuit.num_qubits)
        if isinstance(options,dict) and 'memory' in options:
            memory = options['memory']
        else:
            memory = False
        if circuit.num_clbits == 0:
            circuit = apply_measurement(circuit=circuit,qubits=circuit.qubits)
            if TKET:
                circuit = Tket(circuit, backend_name)
            check_chip_compatiblity(backend, circuit)
            print('Executing Circuit')
            job = execute(circuit, backend=backend, shots=num_shots, memory=memory).result()
        if memory:
            qasm_memory = np.array(job.get_memory(0))
            assert len(qasm_memory)==num_shots
            return qasm_memory
        else:
            counts = job.get_counts(0)
            assert sum(counts.values())==num_shots
            counts = dict_to_array(distribution_dict=counts,force_prob=True)
            return counts
    return None

def read_dict(filename):
    if os.path.isfile(filename):
        f = open(filename,'rb')
        file_content = {}
        while 1:
            try:
                file_content.update(pickle.load(f))
            except (EOFError):
                break
        f.close()
    else:
        file_content = {}
    return file_content

def factor_int(n):
    nsqrt = math.ceil(math.sqrt(n))
    val = nsqrt
    while 1:
        co_val = int(n/val)
        if val*co_val == n:
            return val, co_val
        else:
            val -= 1

def apply_measurement(circuit,qubits):
    measured_circuit = QuantumCircuit(circuit.num_qubits, len(qubits))
    for circuit_inst, circuit_qubits, circuit_clbits in circuit.data:
        measured_circuit.append(circuit_inst,circuit_qubits,circuit_clbits)
    measured_circuit.barrier(qubits)
    measured_circuit.measure(qubits,measured_circuit.clbits)
    return measured_circuit

def generate_circ(num_qubits,depth,circuit_type):
    def gen_secret(num_qubit):
        num_digit = num_qubit-1
        num = 2**num_digit-1
        num = bin(num)[2:]
        num_with_zeros = str(num).zfill(num_digit)
        return num_with_zeros

    i,j = factor_int(num_qubits)
    if circuit_type == 'supremacy_linear':
        full_circ = gen_supremacy(1,num_qubits,depth,regname='q')
    elif circuit_type == 'supremacy':
        if abs(i-j)<=2:
            full_circ = gen_supremacy(i,j,depth,regname='q')
        else:
            full_circ = None
    elif circuit_type == 'hwea':
        full_circ = gen_hwea(i*j,depth,regname='q')
    elif circuit_type == 'bv':
        full_circ = gen_BV(gen_secret(i*j),barriers=False,regname='q')
    elif circuit_type == 'qft':
        full_circ = library.QFT(num_qubits=num_qubits,approximation_degree=0,do_swaps=False)
    elif circuit_type=='aqft':
        approximation_degree=int(math.log(num_qubits,2)+2)
        full_circ = library.QFT(num_qubits=num_qubits,approximation_degree=num_qubits-approximation_degree,do_swaps=False)
    elif circuit_type == 'sycamore':
        full_circ = gen_sycamore(i,j,depth,regname='q')
    elif circuit_type == 'adder':
        if num_qubits%2==0 and num_qubits>2:
            full_circ = gen_adder(nbits=int((num_qubits-2)/2),barriers=False,regname='q')
        else:
            full_circ = None
    elif circuit_type == 'grover':
        if num_qubits%2==0:
            full_circ = gen_grover(width=num_qubits)
        else:
            full_circ = None
    elif circuit_type == 'random':
        full_circ = generate_random_circuit(num_qubits=num_qubits,circuit_depth=depth,density=0.5,inverse=True)
    else:
        raise Exception('Illegal circuit type:',circuit_type)
    assert full_circ.num_qubits==num_qubits or full_circ.num_qubits==0
    return full_circ

def find_process_jobs(jobs,rank,num_workers):
    count = int(len(jobs)/num_workers)
    remainder = len(jobs) % num_workers
    if rank<remainder:
        jobs_start = rank * (count + 1)
        jobs_stop = jobs_start + count + 1
    else:
        jobs_start = rank * count + remainder
        jobs_stop = jobs_start + (count - 1) + 1
    process_jobs = list(jobs[jobs_start:jobs_stop])
    return process_jobs

def evaluate_circ(circuit, backend, options=None, TKET = False):
    if backend not in ["statevector_simulator", "noiseless_qasm_simulator"]:
        fake_backend_data = try_fakeBackend(circuit, backend, options=options, TKET = TKET)
        if fake_backend_data is not None:
            return fake_backend_data
    simulator = aer.Aer.get_backend('aer_simulator')
    if str(backend)=='statevector_simulator':
        circuit.save_statevector()
        result = simulator.run(circuit).result()
        counts = result.get_counts(circuit)
        prob_vector = np.zeros(2**circuit.num_qubits)
        for binary_state in counts:
            state = int(binary_state,2)
            prob_vector[state] = counts[binary_state]
        return prob_vector
    elif str(backend) == 'noiseless_qasm_simulator':
        if isinstance(options,dict) and 'num_shots' in options:
            num_shots = options['num_shots']
        else:
            num_shots = max(1024,2**circuit.num_qubits)

        if isinstance(options,dict) and 'memory' in options:
            memory = options['memory']
        else:
            memory = False
        if circuit.num_clbits == 0:
            circuit.measure_all()
        result = simulator.run(circuit, shots=num_shots, memory=memory).result()

        if memory:
            qasm_memory = np.array(result.get_memory(circuit))
            assert len(qasm_memory)==num_shots
            return qasm_memory
        else:
            noiseless_counts = result.get_counts(circuit)
            assert sum(noiseless_counts.values())==num_shots
            noiseless_counts = dict_to_array(distribution_dict=noiseless_counts,force_prob=True)
            return noiseless_counts
    else:
        raise NotImplementedError

def circuit_stripping(circuit):
    # Remove all single qubit gates and barriers in the circuit
    dag = circuit_to_dag(circuit)
    stripped_dag = DAGCircuit()
    [stripped_dag.add_qreg(x) for x in circuit.qregs]
    for vertex in dag.topological_op_nodes():
        if len(vertex.qargs) == 2 and vertex.op.name!='barrier':
            stripped_dag.apply_operation_back(op=vertex.op, qargs=vertex.qargs)
    return dag_to_circuit(stripped_dag)

def dag_stripping(dag, max_gates):
    '''
    Remove all single qubit gates and barriers in the DAG
    Only leaves the first max_gates gates
    If max_gates is None, do all gates
    '''
    stripped_dag = DAGCircuit()
    [stripped_dag.add_qreg(dag.qregs[qreg_name]) for qreg_name in dag.qregs]
    vertex_added = 0
    for vertex in dag.topological_op_nodes():
        within_gate_count = max_gates is None or vertex_added<max_gates
        if vertex.op.name!='barrier' and len(vertex.qargs)==2 and within_gate_count:
            stripped_dag.apply_operation_back(op=vertex.op, qargs=vertex.qargs)
            vertex_added += 1
    return stripped_dag

def generate_random_circuit(num_qubits, circuit_depth, density, inverse):
    circuit = QuantumCircuit(num_qubits,name='q')
    max_gates_per_layer = int(num_qubits/2)
    num_gates_per_layer = max(int(density*max_gates_per_layer),1)
    # print('Generating %d-q random circuit, density = %d*%d.'%(
    #     num_qubits,num_gates_per_layer,circuit_depth))
    depth_of_random = int(circuit_depth/4) if inverse else int(circuit_depth/2)
    for depth in range(depth_of_random):
        qubit_candidates = list(range(num_qubits))
        num_gates = 0
        while len(qubit_candidates)>=2 and num_gates<num_gates_per_layer:
            qubit_pair = np.random.choice(a=qubit_candidates,replace=False,size=2)
            for qubit in qubit_pair:
                del qubit_candidates[qubit_candidates.index(qubit)]
            # Add a 2-qubit gate
            qubit_pair = [circuit.qubits[qubit] for qubit in qubit_pair]
            circuit.append(instruction=CXGate(),qargs=qubit_pair)
            num_gates += 1
        # Add some 1-qubit gates
        for qubit in range(num_qubits):
            single_qubit_gate = random.choice([IGate(), RZGate(phi=random.uniform(0,np.pi*2)), SXGate(), XGate()])
            circuit.append(instruction=single_qubit_gate,qargs=[qubit])
    if inverse:
        circuit.compose(circuit.inverse(),inplace=True)
        solution_state = np.random.choice(2**num_qubits)
        bin_solution_state = bin(solution_state)[2:].zfill(num_qubits)
        bin_solution_state = bin_solution_state[::-1]
        for qubit_idx, digit in zip(range(num_qubits),bin_solution_state):
            if digit=='1':
                circuit.append(instruction=XGate(),qargs=[circuit.qubits[qubit_idx]])
    return circuit