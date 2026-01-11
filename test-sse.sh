#!/bin/bash
# Test script for donetick MCP SSE endpoint

BASE_URL="${1:-http://192.168.0.4:3456}"

echo "============================================"
echo "Donetick MCP SSE Endpoint Tests"
echo "Base URL: $BASE_URL"
echo "============================================"
echo

# Test 1: Health check
echo "1. Testing health endpoint..."
HEALTH=$(curl -s "$BASE_URL/health")
echo "   Response: $HEALTH"
if echo "$HEALTH" | grep -q '"status":"ok"'; then
    echo "   ✅ Health check PASSED"
else
    echo "   ❌ Health check FAILED"
fi
echo

# Test 2: SSE connection (with and without trailing slash)
echo "2. Testing SSE endpoint..."
echo "   2a. Testing /sse (no trailing slash)..."
SSE_RESPONSE=$(timeout 2 curl -s -v "$BASE_URL/sse" 2>&1 | head -20)
if echo "$SSE_RESPONSE" | grep -q "307 Temporary Redirect"; then
    echo "   → Redirects to /sse/ (expected behavior)"
fi

echo "   2b. Testing /sse/ (with trailing slash)..."
SSE_DATA=$(timeout 3 curl -s -N -H "Accept: text/event-stream" "$BASE_URL/sse/" 2>&1 | head -10)
echo "   Response:"
echo "$SSE_DATA" | sed 's/^/      /'

if echo "$SSE_DATA" | grep -q "event: endpoint"; then
    echo "   ✅ SSE connection PASSED - got endpoint event"
    
    # Extract session ID
    SESSION_ID=$(echo "$SSE_DATA" | grep "data:" | sed 's/.*session_id=//' | tr -d '\n\r')
    echo "   Session ID: $SESSION_ID"
else
    echo "   ❌ SSE connection FAILED - no endpoint event"
fi
echo

# Test 3: Message endpoint (test with fake session - should return error but confirm routing works)
echo "3. Testing message endpoint routing..."
echo "   Testing POST to /sse/messages/..."
MSG_RESPONSE=$(curl -s -X POST "$BASE_URL/sse/messages/?session_id=test123" \
    -H "Content-Type: application/json" \
    -d '{"jsonrpc":"2.0","id":1,"method":"ping","params":{}}' 2>&1)
echo "   Response: $MSG_RESPONSE"

# 400 Bad Request means routing works but session is invalid (expected)
if curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/sse/messages/?session_id=test123" \
    -H "Content-Type: application/json" \
    -d '{}' | grep -q "400\|404\|202"; then
    echo "   ✅ Message endpoint routing PASSED (400/404/202 = endpoint is reachable)"
else
    echo "   ⚠️  Message endpoint may not be correctly routed"
fi
echo

# Test 4: Full MCP handshake simulation
echo "4. Full MCP handshake test..."
echo "   Starting SSE connection and capturing session ID..."

# Start SSE connection in background, capture session ID
SESSION_DATA=$(timeout 5 curl -s -N -H "Accept: text/event-stream" "$BASE_URL/sse/" 2>&1 &
sleep 1
echo "done")

# Parse session from earlier test
if [ -n "$SESSION_ID" ]; then
    echo "   Sending initialize request to session: $SESSION_ID"
    
    INIT_RESPONSE=$(curl -s -X POST "$BASE_URL/sse/messages/?session_id=$SESSION_ID" \
        -H "Content-Type: application/json" \
        -d '{
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            }
        }')
    echo "   Initialize response: $INIT_RESPONSE"
else
    echo "   ⚠️  Could not get session ID for handshake test"
fi
echo

echo "============================================"
echo "Tests Complete"
echo "============================================"
