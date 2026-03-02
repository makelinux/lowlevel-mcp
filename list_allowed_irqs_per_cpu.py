#!/usr/bin/env python3

"""List processes allowed to run on specific CPU.

Returns list of IRQ numbers and process names for processes whose CPU affinity
includes the specified CPU number.
"""

import argparse
from pathlib import Path
from cpu_intersect import parse_cpus_allowed


def get_irq_for_cpu(cpu_num):
    """Get all IRQs allowed to run on specified CPU.

    Args:
        cpu_num: CPU number (0-based)

    Returns:
        List of tuples: [(irq, process_name), ...]
    """
    procs = []
    for p in Path('/proc/irq').glob('[0-9]*'):
        try:
            cpus_allowed = (p / 'smp_affinity').read_text()
            name = "<undefined>"
            for _, dirs, _ in p.walk(top_down=False):
                if len(dirs) > 0:
                    name = dirs[0]

            if cpus_allowed:
                cpus = parse_cpus_allowed(cpus_allowed)
                if int(cpu_num) in cpus:
                    procs.append((int(p.name), name))
        except (PermissionError, FileNotFoundError, ProcessLookupError):
            pass

    return sorted(procs)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='List IRQs allowed to run on specific CPU'
    )
    parser.add_argument('cpu', type=int, help='CPU number (0-based)')
    args = parser.parse_args()

    procs = get_irq_for_cpu(args.cpu)

    if not procs:
        print(f"No IRQs found for CPU {args.cpu}")
    else:
        print(f"IRQs allowed on CPU {args.cpu} ({len(procs)} total):")
        for irq, name in procs:
            print(f"{irq:>6}  {name}")
