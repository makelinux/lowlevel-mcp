#!/usr/bin/env python3
"""
DPDK/SR-IOV performance diagnostic tool.

Checks critical system parameters that affect DPDK/testpmd performance:
- CPU governor, C-states, turbo boost
- CPU isolation and IRQ affinity
- Hugepages configuration
- NIC settings (ring buffers, offloads, queues)
- Thermal and power events
- NUMA alignment
"""
import os
import subprocess
import sys
import re
import json
from pathlib import Path

def run(cmd):
    """Run command and return output."""
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return r.stdout + r.stderr

def check_cpu_governor():
    """Check CPU governor setting."""
    issues = []
    governors = set()

    for cpu_dir in Path('/sys/devices/system/cpu').glob('cpu[0-9]*'):
        gov_file = cpu_dir / 'cpufreq/scaling_governor'
        if gov_file.exists():
            gov = gov_file.read_text().strip()
            governors.add(gov)

    if governors and 'performance' not in governors:
        issues.append(f'CPU governor: {governors} (should be performance)')

    return issues

def check_cstates():
    """Check C-state configuration."""
    issues = []

    # Check C-states via cpuidle
    idle_dir = Path('/sys/devices/system/cpu/cpu0/cpuidle')
    if idle_dir.exists():
        enabled_cstates = []
        for state_dir in idle_dir.glob('state*'):
            disable_file = state_dir / 'disable'
            if disable_file.exists():
                if disable_file.read_text().strip() == '0':
                    state_name = (state_dir / 'name').read_text().strip()
                    enabled_cstates.append(state_name)

        if enabled_cstates and any('C' in s and s != 'C1' for s in enabled_cstates):
            issues.append(f'Deep C-states enabled: {enabled_cstates} (consider disabling for low latency)')

    return issues

def check_turbo_boost():
    """Check Intel Turbo Boost / AMD Turbo Core."""
    issues = []

    # Intel turbo boost
    intel_turbo = Path('/sys/devices/system/cpu/intel_pstate/no_turbo')
    if intel_turbo.exists():
        if intel_turbo.read_text().strip() == '1':
            issues.append('Intel Turbo Boost disabled (enable for max performance)')

    # AMD boost
    amd_boost = Path('/sys/devices/system/cpu/cpufreq/boost')
    if amd_boost.exists():
        if amd_boost.read_text().strip() == '0':
            issues.append('AMD Turbo Core disabled (enable for max performance)')

    return issues

def check_hugepages():
    """Check hugepages configuration."""
    issues = []

    meminfo = Path('/proc/meminfo').read_text()
    hp_total = int(re.search(r'HugePages_Total:\s+(\d+)', meminfo).group(1))
    hp_free = int(re.search(r'HugePages_Free:\s+(\d+)', meminfo).group(1))
    hp_size = int(re.search(r'Hugepagesize:\s+(\d+)', meminfo).group(1))

    if hp_total == 0:
        issues.append('No hugepages configured (required for DPDK)')
    elif hp_free < hp_total * 0.1:
        issues.append(f'Low free hugepages: {hp_free}/{hp_total} (may need more)')

    return issues

def check_irq_affinity(interface):
    """Check IRQ affinity for interface."""
    issues = []

    # Get IRQs for interface
    irqs = run(f"grep {interface} /proc/interrupts | awk '{{print $1}}' | sed 's/:$//'").strip().split('\n')

    for irq in irqs:
        if not irq:
            continue
        affinity_file = f'/proc/irq/{irq}/smp_affinity_list'
        if os.path.exists(affinity_file):
            affinity = Path(affinity_file).read_text().strip()
            # Check if affinity includes CPU 0 (usually housekeeping)
            if '0' in affinity.split(','):
                issues.append(f'IRQ {irq} affined to CPU 0 (consider moving off)')

    return issues

def check_nic_settings(interface):
    """Check NIC configuration."""
    issues = []

    # Ring buffers
    rings = run(f'ethtool -g {interface} 2>/dev/null')
    if 'RX:' in rings:
        rx_match = re.search(r'RX:\s+(\d+)', rings.split('Current')[1])
        if rx_match:
            rx_size = int(rx_match.group(1))
            if rx_size < 256:
                issues.append(f'Small RX ring buffer: {rx_size} (consider 1024+)')

    # Offloads
    offloads = run(f'ethtool -k {interface}')
    if 'large-receive-offload: on' in offloads:
        issues.append('LRO enabled (incompatible with DPDK)')

    if 'rx-vlan-hw-parse: off' in offloads:
        issues.append('RX VLAN parse disabled (required for DPDK)')

    if 'tx-vlan-hw-insert: off' in offloads:
        issues.append('TX VLAN insert disabled (required for DPDK)')

    if 'scatter-gather: off' in offloads:
        issues.append('Scatter-gather disabled (required for DPDK)')

    # Channels
    channels = run(f'ethtool -l {interface} 2>/dev/null')
    if 'Combined:' in channels:
        combined_match = re.search(r'Combined:\s+(\d+)', channels.split('Current')[1])
        if combined_match:
            combined = int(combined_match.group(1))
            if combined < 2:
                issues.append(f'Low queue count: {combined} (consider 4+)')

    return issues

def check_thermal_throttle():
    """Check for thermal throttling events."""
    issues = []

    # Check CPU frequency vs max
    for cpu_dir in Path('/sys/devices/system/cpu').glob('cpu[0-9]*'):
        cur_freq_file = cpu_dir / 'cpufreq/scaling_cur_freq'
        max_freq_file = cpu_dir / 'cpufreq/cpuinfo_max_freq'

        if cur_freq_file.exists() and max_freq_file.exists():
            cur_freq = int(cur_freq_file.read_text().strip())
            max_freq = int(max_freq_file.read_text().strip())

            if cur_freq < max_freq * 0.8:
                cpu_num = cpu_dir.name.replace('cpu', '')
                issues.append(f'CPU {cpu_num} throttled: {cur_freq/1000:.0f}MHz / {max_freq/1000:.0f}MHz max')
                break

    return issues

def check_numa_alignment(interface):
    """Check NUMA node alignment for interface."""
    issues = []

    # Get interface NUMA node
    iface_numa_file = f'/sys/class/net/{interface}/device/numa_node'
    if os.path.exists(iface_numa_file):
        iface_numa = int(Path(iface_numa_file).read_text().strip())

        # Get CPU info
        cpu_numa = {}
        for cpu_dir in Path('/sys/devices/system/cpu').glob('cpu[0-9]*'):
            numa_file = cpu_dir / 'node*/cpulist'
            for nf in cpu_dir.glob('node*/cpulist'):
                numa_node = int(nf.parent.name.replace('node', ''))
                cpu_list = nf.read_text().strip()
                cpu_numa[numa_node] = cpu_list

        if iface_numa >= 0 and iface_numa not in cpu_numa:
            issues.append(f'Interface on NUMA node {iface_numa} with no CPUs')

    return issues

def check_tuned_profile():
    """Check active tuned profile."""
    issues = []

    profile = run('tuned-adm active 2>/dev/null').strip()
    if 'cpu-partitioning' not in profile and 'realtime' not in profile:
        issues.append(f'Tuned profile: {profile} (consider cpu-partitioning for DPDK)')

    return issues

def main():
    interface = sys.argv[1] if len(sys.argv) > 1 else 'wlp0s20f3'

    print(f'DPDK Performance Diagnostic - {interface}\n')

    checks = [
        ('CPU Governor', check_cpu_governor()),
        ('C-states', check_cstates()),
        ('Turbo Boost', check_turbo_boost()),
        ('Hugepages', check_hugepages()),
        ('IRQ Affinity', check_irq_affinity(interface)),
        ('NIC Settings', check_nic_settings(interface)),
        ('Thermal Throttle', check_thermal_throttle()),
        ('NUMA Alignment', check_numa_alignment(interface)),
        ('Tuned Profile', check_tuned_profile()),
    ]

    total_issues = 0
    for name, issues in checks:
        print(f'{name}:')
        if issues:
            for issue in issues:
                print(f'  ⚠ {issue}')
            total_issues += len(issues)
        else:
            print('  ✓ OK')
        print()

    print(f'Total issues: {total_issues}')
    return 1 if total_issues > 0 else 0

if __name__ == '__main__':
    sys.exit(main())
