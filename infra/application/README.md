# Terraform

Run these commands from the repository root.

```bash
uv run python scripts/build_lambda_package.py

terraform -chdir=infra/application init
terraform -chdir=infra/application fmt -check
terraform -chdir=infra/application validate
terraform -chdir=infra/application plan -out=application.tfplan
terraform -chdir=infra/application apply application.tfplan
terraform -chdir=infra/application output
```

## Test the API

Set the Terraform outputs:

```bash
export API_URL="$(terraform -chdir=infra/application output -raw api_url)"
export CLIENT_ID="$(terraform -chdir=infra/application output -raw cognito_client_id)"
export USER_POOL_ID="$(terraform -chdir=infra/application output -raw cognito_user_pool_id)"
export TEST_EMAIL="you@example.com"
export TEST_PASSWORD='Choose-A-Test-Password-123!'
```

Create a Cognito test user:

```bash
aws cognito-idp admin-create-user \
  --user-pool-id "$USER_POOL_ID" \
  --username "$TEST_EMAIL" \
  --user-attributes Name=email,Value="$TEST_EMAIL" Name=email_verified,Value=true \
  --temporary-password "$TEST_PASSWORD" \
  --message-action SUPPRESS

aws cognito-idp admin-set-user-password \
  --user-pool-id "$USER_POOL_ID" \
  --username "$TEST_EMAIL" \
  --password "$TEST_PASSWORD" \
  --permanent
```

Sign in and run the test:

```bash
export ID_TOKEN="$(
  aws cognito-idp initiate-auth \
    --client-id "$CLIENT_ID" \
    --auth-flow USER_PASSWORD_AUTH \
    --auth-parameters USERNAME="$TEST_EMAIL",PASSWORD="$TEST_PASSWORD" \
    --query 'AuthenticationResult.IdToken' \
    --output text
)"

./scripts/test_vpc_api.sh
```

The script sends the ID token as `Authorization: Bearer $ID_TOKEN`, verifies all
three API routes, and offers to delete the test VPC and subnets. The DynamoDB
record remains as test history. The app client has no client secret.

Terraform stores its state in `infra/application/terraform.tfstate`. Keep this file until the deployment is removed.

To remove the application, delete any VPCs created through the API and run:

```bash
terraform -chdir=infra/application destroy
```
