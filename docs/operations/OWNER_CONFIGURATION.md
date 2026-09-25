# Owner Configuration Status

`config/owner.yaml` is absent. The example is private-by-default with INR, Asia/Kolkata and three markets as editable assumptions. It now exposes `storage_budget.max_gib`, `backup_location`, `market_data_budget`, `AI_model_budget`, and `ai_privacy.cloud_model_allowed`, `portfolio_context_allowed_for_cloud`, `journal_context_allowed_for_cloud`. The three privacy flags default false. `AI_model_budget` does not affect Phase 1A except cost policy. Never store secrets in this YAML or Git.

**Required before Phase 1A:** actual base currency, IANA timezone, enabled markets, disk budget, separate backup destination, data budget and privacy flags. The owner can leave research horizon and review times as examples. Credentials should come from local environment or OS keychain at probe/runtime. A copied example with null budget/location does not count as validated configuration.
