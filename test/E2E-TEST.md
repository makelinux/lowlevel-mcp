# End-to-End Testing

This directory contains end-to-end tests for lowlevel-mcp integration with OpenShift Lightspeed (OLS).

## Prerequisites

- lowlevel-mcp deployed to cluster
- OpenShift Lightspeed (OLS) deployed and configured with lowlevel-mcp
- oc access to cluster
- Python 3 with requests module on local machine
- ols_query.py in the lowlevel-mcp directory

## Running the test

```bash
./test-e2e.sh
```

Verbose mode (prints full OLS responses):

```bash
./test-e2e.sh -v
```

## Configuration

The test uses these defaults:
- OLS namespace: `openshift-lightspeed`
- OLS service: `lightspeed-app-server`
- OLS port: `8443`
- lowlevel-mcp namespace: `lowlevel-mcp`

- `OLS_TOKEN` - Authentication token (default: from `oc whoami -t`)

Example with custom token:

```bash
export OLS_TOKEN=$(oc create token ols-query -n openshift-lightspeed --duration=24h)
./test-e2e.sh
```

## Tests

The e2e test suite includes:

1. **CPU process listing** - Verifies lowlevel-mcp can list processes allowed on CPU 0 via OLS
2. **Ethtool query** - Verifies lowlevel-mcp can query network interface settings via OLS
3. **IRQ listing** - Verifies lowlevel-mcp can list IRQs allowed on CPU 0 via OLS

## Expected output

```
lowlevel-mcp deployment OK
port-forward OK
OLS token OK
Test 1: List processes on CPU 0 Pass
Test 2: Query ethtool ring settings Pass
Test 3: List IRQs on CPU 0 Pass
```

## Troubleshooting

**Error: lowlevel-mcp daemonset not found**
- Ensure lowlevel-mcp is deployed: `oc get ds -n lowlevel-mcp`

**Error: Could not get OLS token**
- Ensure you're logged in: `oc whoami`
- Check if you can get token: `oc whoami -t`
- Or set OLS_TOKEN manually: `export OLS_TOKEN=your-token`

**Error: Port-forward failed to establish**
- Check OLS is deployed: `oc get svc -n openshift-lightspeed`
- Verify service name matches OLS_SERVICE
- Check if port 8443 is already in use: `lsof -i :8443`

**Test failures**
- Check lowlevel-mcp logs: `oc logs -n lowlevel-mcp -l app=lowlevel-mcp`
- Check OLS logs: `oc logs -n openshift-lightspeed -l app=lightspeed-app-server -c lightspeed-service-api`
- Verify OLS configuration includes lowlevel-mcp: `oc get olsconfig cluster -o yaml`
