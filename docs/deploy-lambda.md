# Gatehouse deployment notes (doc 09 companion)

## Package layout inside Lambda

The SAM template deploys with two artifacts, assembled by `scripts/build_lambda.sh`:

1. **Source zip** (`CodeUri: build/lambda-src`): the repo's `src/gatehouse`
   tree re-rooted so that `gatehouse/` is importable at the function root,
   plus the India country pack YAML. Pure Python, platform-independent.
2. **Dependencies layer** (ARM64 manylinux wheels): pydantic, pydantic-settings,
   fastapi, mangum, strands-agents, boto3, PyYAML, httpx and their transitive
   deps, downloaded by pip for `manylinux2014_aarch64` + `cp312` so no Docker
   daemon is required and the binary surface matches the arm64 runtime.

`GATEHOUSE_PACK_PATH` points the runtime at `/opt/packs/in/pack.yaml` inside
Lambda; local dev keeps using the repo path by default.

## Deploy commands

```bash
bash scripts/build_lambda.sh
sam validate --template-file template.yaml --region ap-south-1
sam deploy --guided --capabilities CAPABILITY_NAMED_IAM \
  --region ap-south-1 --stack-name gatehouse-staging
```

Parameters asked during guided deploy:

| Parameter | Source |
|---|---|
| TelegramWebhookSecret | long random string, same value later given to setWebhook |
| TelegramBotToken | from BotFather |
| GuardianChatId | guardian chat id (bot must receive one message first) |
| GraphSalt | long random string per environment |

## Webhook registration

After deploy, read `ApiBase` from the stack outputs and run
`scripts/set_webhook.py <api-base>`, which registers

    https://<api-id>.execute-api.ap-south-1.amazonaws.com/staging/telegram

with the secret token header contract, then verifies via getWebhookInfo.
