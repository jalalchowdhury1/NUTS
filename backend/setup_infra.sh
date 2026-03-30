#!/usr/bin/env bash
# =============================================================================
# NUTS Algo — AWS Infrastructure Setup
#
# Creates:
#   1. S3 bucket          nuts-algo-data
#   2. EventBridge rule   nuts-compute      (every 30 min on market hours)
#   3. EventBridge rule   nuts-update-prices (daily after market close)
#   4. Prints the IAM policy JSON the Lambda execution role needs
#
# Prerequisites:
#   - AWS CLI v2 configured with a profile that has sufficient permissions
#   - Lambda function already deployed; set LAMBDA_ARN below before running
#   - jq (optional, for pretty-printing the policy at the end)
#
# Usage:
#   export LAMBDA_ARN="arn:aws:lambda:us-east-1:123456789012:function:nuts-algo"
#   export AWS_REGION="us-east-1"          # defaults to us-east-1
#   chmod +x setup_infra.sh && ./setup_infra.sh
# =============================================================================

set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────
BUCKET="nuts-algo-data"
REGION="${AWS_REGION:-us-east-1}"
LAMBDA_ARN="${LAMBDA_ARN:?ERROR: Set LAMBDA_ARN before running this script}"

# Derive the account ID and Lambda function name from the ARN
ACCOUNT_ID=$(echo "$LAMBDA_ARN" | cut -d: -f5)
FUNCTION_NAME=$(echo "$LAMBDA_ARN" | cut -d: -f7)

echo "=================================================================="
echo " NUTS Algo Infrastructure Setup"
echo " Region:   $REGION"
echo " Bucket:   $BUCKET"
echo " Lambda:   $FUNCTION_NAME  ($LAMBDA_ARN)"
echo " Account:  $ACCOUNT_ID"
echo "=================================================================="


# ── 1. S3 Bucket ─────────────────────────────────────────────────────────────
echo ""
echo "▶ Step 1: Creating S3 bucket s3://${BUCKET} ..."

if [ "$REGION" = "us-east-1" ]; then
  # us-east-1 does NOT accept a LocationConstraint — omit it entirely
  aws s3api create-bucket \
    --bucket "$BUCKET" \
    --region "$REGION" \
    2>&1 | grep -v "BucketAlreadyOwnedByYou" || true
else
  aws s3api create-bucket \
    --bucket "$BUCKET" \
    --region "$REGION" \
    --create-bucket-configuration LocationConstraint="$REGION" \
    2>&1 | grep -v "BucketAlreadyOwnedByYou" || true
fi

# Block all public access
aws s3api put-public-access-block \
  --bucket "$BUCKET" \
  --public-access-block-configuration \
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

echo "   ✓ Bucket ready: s3://${BUCKET}"


# ── 2. EventBridge rule — 30-minute compute schedule ─────────────────────────
# Fires at :05 and :35 past the hour, 13:00–20:00 UTC (09:00–16:00 ET)
# on NYSE trading days (Mon–Fri).  Passes {"action":"compute"} to Lambda.
echo ""
echo "▶ Step 2: Creating EventBridge rule 'nuts-compute' ..."

COMPUTE_RULE_ARN=$(aws events put-rule \
  --name "nuts-compute" \
  --schedule-expression "cron(5,35 13-20 ? * MON-FRI *)" \
  --state ENABLED \
  --description "NUTS Algo: force-recompute signal every 30 min during market hours" \
  --region "$REGION" \
  --query "RuleArn" \
  --output text)

echo "   Rule ARN: $COMPUTE_RULE_ARN"

aws events put-targets \
  --rule "nuts-compute" \
  --region "$REGION" \
  --targets "[
    {
      \"Id\": \"nuts-lambda-compute\",
      \"Arn\": \"${LAMBDA_ARN}\",
      \"Input\": \"{\\\"action\\\":\\\"compute\\\"}\"
    }
  ]"

# Grant EventBridge permission to invoke the Lambda
aws lambda add-permission \
  --function-name "$FUNCTION_NAME" \
  --statement-id "AllowEventBridgeCompute" \
  --action "lambda:InvokeFunction" \
  --principal "events.amazonaws.com" \
  --source-arn "$COMPUTE_RULE_ARN" \
  --region "$REGION" \
  2>&1 | grep -v "ResourceConflictException" || true

echo "   ✓ nuts-compute rule and Lambda permission created"


# ── 3. EventBridge rule — daily price update ──────────────────────────────────
# Fires at 21:00 UTC (17:00 ET) Mon–Fri — after market close and settlement.
# Passes {"action":"update_prices"} to Lambda.
echo ""
echo "▶ Step 3: Creating EventBridge rule 'nuts-update-prices' ..."

UPDATE_RULE_ARN=$(aws events put-rule \
  --name "nuts-update-prices" \
  --schedule-expression "cron(0 21 ? * MON-FRI *)" \
  --state ENABLED \
  --description "NUTS Algo: fetch and persist today's closing prices to S3" \
  --region "$REGION" \
  --query "RuleArn" \
  --output text)

echo "   Rule ARN: $UPDATE_RULE_ARN"

aws events put-targets \
  --rule "nuts-update-prices" \
  --region "$REGION" \
  --targets "[
    {
      \"Id\": \"nuts-lambda-update-prices\",
      \"Arn\": \"${LAMBDA_ARN}\",
      \"Input\": \"{\\\"action\\\":\\\"update_prices\\\"}\"
    }
  ]"

aws lambda add-permission \
  --function-name "$FUNCTION_NAME" \
  --statement-id "AllowEventBridgeUpdatePrices" \
  --action "lambda:InvokeFunction" \
  --principal "events.amazonaws.com" \
  --source-arn "$UPDATE_RULE_ARN" \
  --region "$REGION" \
  2>&1 | grep -v "ResourceConflictException" || true

echo "   ✓ nuts-update-prices rule and Lambda permission created"


# ── 4. IAM Policy JSON ────────────────────────────────────────────────────────
# Attach this policy to the Lambda execution role so it can read/write S3.
# Replace <YOUR_LAMBDA_ROLE_NAME> with the actual role, then run:
#
#   aws iam put-role-policy \
#     --role-name <YOUR_LAMBDA_ROLE_NAME> \
#     --policy-name NutsAlgoS3Access \
#     --policy-document file://nuts_s3_policy.json
#
echo ""
echo "▶ Step 4: Writing IAM policy to nuts_s3_policy.json ..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cat > "${SCRIPT_DIR}/nuts_s3_policy.json" << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "NutsAlgoS3ReadWrite",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": "arn:aws:s3:::${BUCKET}/*"
    },
    {
      "Sid": "NutsAlgoS3List",
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::${BUCKET}"
    }
  ]
}
EOF

echo "   ✓ Policy written to ${SCRIPT_DIR}/nuts_s3_policy.json"
echo ""
echo "   To attach to your Lambda role, run:"
echo "   aws iam put-role-policy \\"
echo "     --role-name <YOUR_LAMBDA_ROLE_NAME> \\"
echo "     --policy-name NutsAlgoS3Access \\"
echo "     --policy-document file://${SCRIPT_DIR}/nuts_s3_policy.json"


# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "=================================================================="
echo " Setup complete."
echo " Next steps:"
echo "   1. Attach nuts_s3_policy.json to the Lambda execution role"
echo "   2. Deploy the updated Lambda package (run deploy.sh)"
echo "   3. Run bootstrap_historical.py to seed the S3 price CSVs"
echo "   4. Test via: aws lambda invoke --function-name $FUNCTION_NAME \\"
echo "        --payload '{\"action\":\"compute\"}' /tmp/out.json"
echo "=================================================================="
