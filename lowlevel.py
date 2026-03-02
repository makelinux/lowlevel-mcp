"""Low-level system diagnostics MCP server.

Provides tools for CPU affinity analysis, MSR register access, and ethtool queries.
"""
from typing import Annotated, Literal
import subprocess
import sys
import os
from fastmcp import FastMCP
import cpu_intersect
import list_allowed_irqs_per_cpu
import list_allowed_processes_per_cpu

import autodoc

# Initialize FastMCP server
mcp = FastMCP("lowlevel")

@mcp.tool()
def find_cpu_intersections(
    cpus: str = "",
    ignore_cgroups: str = "",
    ignore_procs: str = "",
) -> str:
    """Find processes with intersecting CPU affinity from different cgroups.

    Args:
        cpus: Filter by CPU list (e.g., "0,1,2")
        ignore_cgroups: Ignore cgroups (comma-separated)
        ignore_procs: Ignore process names (comma-separated)

    Returns:
        Report of cgroup pairs with overlapping CPU sets
    """
    cpu_filter = None
    if cpus:
        cpu_filter = {int(c.strip()) for c in cpus.split(',') if c.strip()}

    ignore_cg = {cg.strip() for cg in ignore_cgroups.split(',') if cg.strip()} if ignore_cgroups else set()
    ignore_pr = {p.strip() for p in ignore_procs.split(',') if p.strip()} if ignore_procs else set()

    procs = cpu_intersect.get_proc_info(cpu_filter, ignore_cg, ignore_pr)
    mismatches = cpu_intersect.find_cgroup_mismatches(procs)

    output = []
    if not mismatches:
        output.append("No processes with intersecting CPUs and mismatched cgroups found")
    else:
        for pid1, pid2, shared in mismatches:
            p1 = procs[pid1]
            p2 = procs[pid2]
            output.append(f"{pid1:>6} {p1['name']:20} cgroup {p1['cgroup']}")
            output.append(f"{pid2:>6} {p2['name']:20} cgroup {p2['cgroup']}")
            output.append(f"       Shared CPUs: {cpu_intersect.fmt_cpus(shared)}\n")

    return "\n".join(output)

@mcp.tool(annotations={
            "readOnlyHint": True,
            "destructiveHint": False
            }
)
def list_processes_for_cpu(
        cpu: Annotated[int, "CPU number (0-based)"]
    ) -> str:
    """List all processes allowed to run on specified CPU.

    Args:
        cpu: CPU number (0-based)

    Returns:
        List of PIDs and process names for the specified CPU
    """
    procs = list_allowed_processes_per_cpu.get_processes_for_cpu(cpu)

    if not procs:
        return f"No processes found for CPU {cpu}"

    output = [f"Processes allowed on CPU {cpu} ({len(procs)} total):"]
    for pid, name in procs:
        output.append(f"{pid:>6}  {name}")

    return "\n".join(output)


@mcp.tool(annotations={
            "readOnlyHint": True,
            "destructiveHint": False
            }
)
def list_irqs_for_cpu(
        cpu: Annotated[int, "CPU number (0-based)"]
    ) -> str:
    """List all IRQs that are allowed to run on specified CPU.

    Args:
        cpu: CPU number (0-based)

    Returns:
        List of IRQs and process names for the specified CPU. If no process
        name is found, it will be listed as <undefined>.
    """
    procs = list_allowed_irqs_per_cpu.get_irq_for_cpu(cpu)

    if not procs:
        return f"No IRQs found for CPU {cpu}"

    output = [f"IRQs allowed on CPU {cpu} ({len(procs)} total):"]
    for irq, name in procs:
        output.append(f"{irq:>6}  {name}")

    return "\n".join(output)


@mcp.tool(annotations={
            "readOnlyHint": True,
            "destructiveHint": False
            }
)
def read_msr_register(
        register: Annotated[str, "Hexadecimal number for the register to be read"],
        cpu: Annotated[int, "If specified, read the register from this CPU. Defaults to 0"] = 0
    ) -> str:
    """Read an MSR register from the specified CPU.

    Returns:
        The MSR register value, in hexadecimal.
    """
    args = ["/usr/sbin/rdmsr", "-x", "-p", str(cpu), register]
    if os.getuid() != 0:
        args = ['sudo'] + args
    result = subprocess.run(args, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        return f"Error: {result.stderr}\n"
    return result.stdout

@mcp.tool(annotations={
            "readOnlyHint": True,
            "destructiveHint": False
            }
)
def query_ethtool(
        interface: Annotated[str, "Network interface name (e.g., eth0)"],
        query: Annotated[Literal["show-coalesce", "show-ring", "driver", "show-offload",
                                 "statistics", "show-channels"],
                                 "Query type: must be one of show-coalesce, show-ring, driver, "
                                 "show-offload, statistics, show-channels"]
    ) -> str:
    """Query ethtool for network interface information.

    Args:
        interface: Network interface name
        query: One of: show-coalesce, show-ring, driver, show-offload, statistics, show-channels

    Returns:
        Raw ethtool command output
    """
    r = subprocess.run(['/usr/sbin/ethtool', f'--{query}', interface],
                       text=True, capture_output=True, check=False)
    if r.returncode != 0:
        return f"Error: {r.stderr}"
    return r.stdout


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == '--help':
            autodoc.show_autodoc(sys.modules[__name__])
        else:
            a1 = sys.argv[1]
            sys.argv = sys.argv[1:]
            if '(' in a1:
                ret = eval(a1)
            else:
                ret = eval(a1 + '(' + ', '.join("'%s'" % (a) for a in sys.argv[1:]) + ')')
            print(ret)
    else:
        mcp.run(transport="http", host="0.0.0.0", port=9028)
