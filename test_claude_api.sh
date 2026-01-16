#!/bin/bash

# Test Claude API directly
# Usage: ./test_claude_api.sh YOUR_API_KEY

API_KEY="${1:-$ANTHROPIC_API_KEY}"
MODEL="claude-3-haiku-20240307"

if [ -z "$API_KEY" ]; then
    echo "❌ Error: API key required"
    echo "Usage: $0 YOUR_API_KEY"
    echo "Or set ANTHROPIC_API_KEY environment variable"
    exit 1
fi

echo "🧪 Testing Claude API with model: $MODEL"
echo "📝 Request body:"
cat <<EOF | jq .
{
  "model": "$MODEL",
  "max_tokens": 4096,
  "messages": [
    {
      "role": "user",
      "content": "Tell me a joke"
    }
  ]
}
EOF

echo ""
echo "📤 Sending request..."
echo ""

curl -X POST "https://api.anthropic.com/v1/messages" \
  -H "x-api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -H "anthropic-version: 2023-06-01" \
  -d "{
    \"model\": \"$MODEL\",
    \"max_tokens\": 4096,
    \"messages\": [
      {
        \"role\": \"user\",
        \"content\": \"Tell me a joke\"
      }
    ]
  }" | jq .

echo ""
echo "✅ Test complete"
