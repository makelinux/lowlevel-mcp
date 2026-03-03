# Low-level MCP Server

This MCP server is meant to expose certain low level information from an OpenShift
node, to be consumed by LLMs that require this type of information for
troubleshooting purposes.

## Deployment

The MCP Server is typically deployed as a Kubernetes Deployment with a
Service. See the `deploy/` directory for manifests.

A `Makefile` is provided for convenience, with tools to build/push the container
image, and then deploy/undeploy the MCP server.

## Running locally

```bash
pip install -r requirements.txt
python lowlevel.py
```

## Tools

The MCP server exposes the following tools:

### `find_cpu_intersections`

Find processes with intersecting CPU affinity that belong to different cgroups.
This is useful for detecting CPU affinity conflicts between Kubernetes pods,
systemd services, or containers sharing the same node.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `cpus` | string | No | Filter by CPU list (e.g., `"0,1,2"`) |
| `ignore_cgroups` | string | No | Cgroup names to ignore, comma-separated |
| `ignore_procs` | string | No | Process names to ignore, comma-separated |

**Returns:** A report listing cgroup pairs with overlapping CPU sets, including
the PIDs, process names, cgroup identifiers, and the shared CPUs for each
conflicting pair.

### `list_processes_for_cpu`

List all processes whose CPU affinity allows them to run on a specified CPU.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `cpu` | int | Yes | CPU number (0-based) |


**Returns:** A list of PIDs and process names for every process allowed to run
on the given CPU.

### `list_irqs_for_cpu`

List all IRQs whose CPU affinity allows them to run on a specified CPU.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `cpu` | int | Yes | CPU number (0-based) |

**Returns:** A list of IRQ numbers and process names for every IRQ allowed to run
on the given CPU.  If there is no process name found, it will be listed as
`<undefined>`.


### `read_msr_register`

Read a Model-Specific Register (MSR) from a given CPU. Requires `rdmsr`
(`/usr/sbin/rdmsr`) to be available on the host.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `register` | string | Yes | Hexadecimal address of the MSR to read (e.g., `"0x1a0"`) |
| `cpu` | int | No | CPU to read the register from (0-based, defaults to 0) |

**Returns:** The register value in hexadecimal.

### `query_ethtool`

Run an ethtool query from an interface. It requires the `ethtool` binary to be
available on the host under `/usr/sbin`. 

Note that only certain `ethtool` queries are supported, and all those are read-only
and will not change any network interface configuration.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `interface` | string | Yes | Network interface name (e.g., `"ens1f0"`) |
| `query` | Literal | Yes | Query type: must be one of show-coalesce, show-ring, driver, show-offload, statistics, show-channels |

**Returns:** The raw ethtool command output.

## Testing

### End-to-end test

Test the lowlevel-mcp integration with OpenShift Lightspeed:

```bash
cd test && ./test-e2e.sh
```

See [test/E2E-TEST.md](test/E2E-TEST.md) for details.

## Dependencies

- [FastMCP](https://gofastmcp.com/) (>= 3.0.0b2) -- MCP server and client framework
