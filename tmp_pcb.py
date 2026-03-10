import json
from pcb import generate_pcb
schematic = {
    'modules': [
        {'instanceId': 'U1', 'moduleName': 'A', 'pins': [], 'pcb_meta': {'width_mm': 5, 'height_mm': 5}},
        {'instanceId': 'U2', 'moduleName': 'B', 'pins': [], 'pcb_meta': {'width_mm': 5, 'height_mm': 5}},
        {'instanceId': 'U3', 'moduleName': 'C', 'pins': [], 'pcb_meta': {'width_mm': 5, 'height_mm': 5}}
    ],
    'wires': [
        {'fromInstanceId': 'U1', 'fromPinId': 'pin1', 'toInstanceId': 'U2', 'toPinId': 'pin1'},
        {'fromInstanceId': 'U2', 'fromPinId': 'pin1', 'toInstanceId': 'U3', 'toPinId': 'pin1'}
    ]
}
result = generate_pcb(schematic)
print(json.dumps(result, indent=2))
