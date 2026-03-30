#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# NUTS Algo — Deploy backend to AWS Lambda
#
# Usage:
#   ./deploy.sh                  # deploy code only (Lambda function)
#   ./deploy.sh --create-layer   # build & publish the dependency layer first
#
# Requires: AWS CLI configured with us-east-1 access
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

FUNCTION_NAME="nuts-visualizer"
REGION="us-east-1"
LAYER_NAME="nuts-visualizer-deps"
RUNTIME="python3.10"
ZIP_FILE="nuts_deployment.zip"
LAYER_ZIP="nuts_layer.zip"

echo "🚀 NUTS Algo — Lambda Deploy"
echo "    Function : $FUNCTION_NAME"
echo "    Region   : $REGION"
echo ""

# ── Clean previous artifacts ─────────────────────────────────────────────────
echo "🧹 Cleaning previous build artifacts..."
rm -rf lambda_package nuts_layer "$ZIP_FILE" "$LAYER_ZIP"

# ── Optional: build dependency layer ─────────────────────────────────────────
if [[ "${1:-}" == "--create-layer" ]]; then
    echo ""
    echo "📦 Building Lambda Layer (deps)..."
    mkdir -p nuts_layer/python

    pip install \
        yfinance pandas numpy pytz requests \
        -t nuts_layer/python/ \
        --platform manylinux2014_x86_64 \
        --implementation cp \
        --python-version 3.10 \
        --only-binary=:all: \
        --upgrade \
        --quiet

    cd nuts_layer
    zip -r "../$LAYER_ZIP" python/ -q
    cd ..

    LAYER_SIZE=$(du -sh "$LAYER_ZIP" | cut -f1)
    echo "   Layer zip size: $LAYER_SIZE"

    echo "📤 Publishing layer to AWS..."
    LAYER_VERSION=$(aws lambda publish-layer-version \
        --layer-name "$LAYER_NAME" \
        --zip-file "fileb://$LAYER_ZIP" \
        --compatible-runtimes "$RUNTIME" \
        --region "$REGION" \
        --query "Version" \
        --output text)

    LAYER_ARN="arn:aws:lambda:${REGION}:$(aws sts get-caller-identity --query Account --output text):layer:${LAYER_NAME}:${LAYER_VERSION}"
    echo "✅ Layer published: $LAYER_ARN"
    echo ""
    echo "   Run this to attach the layer to the function:"
    echo "   aws lambda update-function-configuration \\"
    echo "     --function-name $FUNCTION_NAME \\"
    echo "     --layers $LAYER_ARN \\"
    echo "     --region $REGION"
    echo ""
fi

# ── Package Lambda function code (NO dependencies — they're in the Layer) ────
echo "📦 Packaging Lambda function code..."
mkdir -p lambda_package/trees

# Copy top-level Python modules
cp lambda_function.py  lambda_package/
cp calculations.py     lambda_package/
cp data_fetcher.py     lambda_package/
cp data_manager.py     lambda_package/
cp state_manager.py    lambda_package/

# Copy trees package
cp trees/__init__.py   lambda_package/trees/
cp trees/frontrunners.py lambda_package/trees/
cp trees/ftlt.py         lambda_package/trees/
cp trees/blackswan.py    lambda_package/trees/

# Zip
cd lambda_package
zip -r "../$ZIP_FILE" . -q
cd ..

ZIP_SIZE=$(du -sh "$ZIP_FILE" | cut -f1)
echo "   Code zip size: $ZIP_SIZE"

# ── Upload to Lambda ──────────────────────────────────────────────────────────
echo ""
echo "📤 Uploading to Lambda..."
aws lambda update-function-code \
    --function-name "$FUNCTION_NAME" \
    --zip-file "fileb://$ZIP_FILE" \
    --region "$REGION" \
    --output text \
    --query "CodeSize" \
    | xargs -I{} echo "   Deployed {} bytes"

echo ""
echo "✅ Deploy complete!"
echo ""

# ── Print the API Gateway URL ─────────────────────────────────────────────────
echo "🌐 API Gateway URL:"
aws apigatewayv2 get-apis \
    --region "$REGION" \
    --query "Items[?Name=='nuts-visualizer-api'].ApiEndpoint | [0]" \
    --output text 2>/dev/null || echo "   (run aws apigatewayv2 get-apis to find your URL)"
