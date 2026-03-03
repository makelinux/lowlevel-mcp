#!/bin/bash
# End-to-end test for lowlevel-mcp integration with OLS

set -e

die() { echo "$@" >&2; exit 1; }

err_handler() {
	local line=$1
	echo "ERROR at line $line" >&2
	exit 1
}

verbose=false
[ "$1" = "-v" ] || [ "$1" = "--verbose" ] && verbose=true

orig_ns=$(oc config view --minify -o jsonpath='{..namespace}')
oc config set-context --current --namespace=lowlevel-mcp >/dev/null

cleanup() {
	kill $pf_pid 2>/dev/null || true
	test -n "$orig_ns" && oc config set-context --current --namespace="$orig_ns" >/dev/null 2>&1 || true
}

trap 'err_handler $LINENO' ERR
trap cleanup EXIT

echo -n "lowlevel-mcp deployment "
oc get daemonset lowlevel-mcp >/dev/null ||
	die "lowlevel-mcp daemonset not found"
pod_status=$(oc get pods -l app=lowlevel-mcp -o jsonpath='{.items[0].status.phase}')
test "$pod_status" = "Running" && echo "OK" ||
	die "pod not running (status: $pod_status)"

echo -n "port-forward "
oc port-forward -n openshift-lightspeed svc/lightspeed-app-server 8443:8443 >/dev/null 2>&1 &
pf_pid=$!
sleep 5
curl -k --max-time 2 https://localhost:8443 >/dev/null 2>&1 && echo "OK" ||
	{ kill $pf_pid 2>/dev/null; die "failed"; }

export OLS_BASE_URL="https://localhost:8443"

echo -n "OLS token "
test -n "$OLS_TOKEN" || OLS_TOKEN=$(oc whoami -t 2>/dev/null)
test -n "$OLS_TOKEN" && echo "OK" ||
	die "failed to get from 'oc whoami -t'"
export OLS_TOKEN

echo -n "Test 1: List processes on CPU 0 "
output1=$(./ols_query.py "Use lowlevel MCP to just list processes allowed on CPU 0")
$verbose && { echo ""; echo "--- Response:"; echo "$output1"; echo "---"; }
echo "$output1" | grep -qiE 'systemd|kthreadd|process' && echo "Pass" ||
	{ echo "$output1" | head -20; die "FAILED"; }

echo -n "Test 2: Query ethtool ring settings "
pod=$(oc get pods -l app=lowlevel-mcp -o jsonpath='{.items[0].metadata.name}')
iface=$(oc exec $pod -- sh -c 'ls /sys/class/net | grep -m1 -E "^(ens|eth|eno)"')
ethtool=$(./ols_query.py "Use lowlevel MCP to query ethtool ring settings for interface $iface")
$verbose && { echo ""; echo "--- Response:"; echo "$ethtool"; echo "---"; }
echo "$ethtool" | grep -qiE 'ring|rx|tx' && echo "Pass" ||
	{ echo "$ethtool" | head -20; die "FAILED"; }

echo -n "Test 3: List IRQs on CPU 0 "
list_irqs_for_cpu=$(./ols_query.py "Use lowlevel MCP tool to list IRQs for CPU 0")
$verbose && { echo ""; echo "--- Response:"; echo "$list_irqs_for_cpu"; echo "---"; }
echo "$list_irqs_for_cpu" | grep -qiE 'irq' && echo "Pass" ||
	{ echo "$list_irqs_for_cpu" | head -20; die "FAILED"; }
