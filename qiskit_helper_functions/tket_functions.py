from pytket.routing import Architecture, route, place_with_map
from pytket.transform import Transform
from pytket.routing import Placement, LinePlacement, GraphPlacement, NoiseAwarePlacement
from pytket.extensions.qiskit import qiskit_to_tk, tk_to_qiskit

def Tket(circuit, backend = None, transform = False):
    pytket_circ = qiskit_to_tk(circuit)

    backend = get_backend_name(backend)
    backend = available_backend[backend]
    backend = backend()
    check_chip_compatiblity(backend, circuit) # Validate Chip Size to Circuit Size

    if transform:
        Transform.RemoveRedundancies().apply(physical_c)
        Transform.OptimisePostRouting().apply(physical_c)
        Transform.RebaseToQiskit().apply(physical_c)


    arc = Architecture(backend._configuration.coupling_map)

    # placement = Placement(arc)
    # placement_map = placement.get_placement_map(pytket_circ)

    physical_c = route(pytket_circ, arc)

    # placement.place(physical_c)
    # place_with_map(pytket_circ, placement_map)

    final_circ = tk_to_qiskit(physical_c)

    return final_circ

from qiskit.circuit import QuantumRegister, Qubit
from pprint import pprint
def tket_path(pathmap):
    map = pathmap.copy()
    q_node = Qubit(QuantumRegister(6, 'q'), 0)
    q_node.register.size, q_node.index
    
    for key, values in map.items():
        for index, conn in enumerate(map[key]): 
            # {'subcircuit_idx': 0, 'subcircuit_qubit': Qubit(QuantumRegister(4, 'q'), 0)}
            qubit = conn['subcircuit_qubit']
            qubit = Qubit(QuantumRegister(qubit.register.size, 'node'), qubit.index)
            qubit._hash = pathmap[key][index]['subcircuit_qubit']._hash
            map[key][index]['subcircuit_qubit'] = qubit
    return map

from qiskit import QuantumCircuit, QuantumRegister
def tket_rename_nodes(circuit):
    qreg = QuantumRegister(circuit.num_qubits , 'q')
    if circuit.cregs:
        creg = QuantumRegister(len(circuit.cregs) , 'c')
        circ = QuantumCircuit(qreg, creg)
    else:
        circ = QuantumCircuit(qreg)

    for instr, qargs, cargs in circuit._data:
        qreg = [ reg.index for reg in qargs ]
        circ.append(instr, qreg)

    return circ