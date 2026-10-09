# Changelog

## 1.0.0 (2026-10-09)


### Features

* add access_code table for employee invites ([6f51dbe](https://github.com/Solierrr/database-console/commit/6f51dbe3f0e9a5edfe71cbf1e2ce714907436807))
* add business-rule functions and procedures for proposals and service execution ([a151d9c](https://github.com/Solierrr/database-console/commit/a151d9cc52e3a60da7953030af2b8aea41f9b8ba))
* add connect target to open a psql session against a target database ([603c37e](https://github.com/Solierrr/database-console/commit/603c37ee08aef5d41a3fdabd390f10c706f610b1))
* add connect target to open a psql session against a target database ([0852157](https://github.com/Solierrr/database-console/commit/0852157bd0cc127df294a3480501670d76f57211))
* add data catalog table and documented backup/recovery runbook ([08ad305](https://github.com/Solierrr/database-console/commit/08ad305b16ee124785542ad3473ee37158e0c1cb))
* add faker-based dataload script for the normalized schema ([9c17b3d](https://github.com/Solierrr/database-console/commit/9c17b3db4ed6660b391f2410994bf328b4d09bf9))
* add generic audit trigger and attach it to critical business tables ([d1d63fe](https://github.com/Solierrr/database-console/commit/d1d63fea667a89a7c801749b0b8e0212f47deda8))
* add migrations for company type/slug and catalog profile contract ([9e65ed5](https://github.com/Solierrr/database-console/commit/9e65ed5b6ab2baa9802fafbde64889eb2d170e5c))
* add operational access permissions and review status ([bfd5316](https://github.com/Solierrr/database-console/commit/bfd5316a8d3d368b0b1facdee4b790aaef2215da))
* add performance indexes backed by measured explain analyze results ([88e13ce](https://github.com/Solierrr/database-console/commit/88e13ce5760102cb6d40e65db594f63b45d72262))
* add platform_admin table and a demo platform admin user ([a8f0fff](https://github.com/Solierrr/database-console/commit/a8f0fff74439ec25b36f4d7ef038d34a1776f613))
* add recursive cte function to trace refresh token rotation lineage ([dd16634](https://github.com/Solierrr/database-console/commit/dd16634d4fbc81970f638523f695bcb73b689e0b))
* add star-schema bi views with cte and window functions ([a9ef073](https://github.com/Solierrr/database-console/commit/a9ef0732261416c54e69e8743e65304e8f3c1369))
* adiciona username e banner ao usuario ([#12](https://github.com/Solierrr/database-console/issues/12)) ([385ca6d](https://github.com/Solierrr/database-console/commit/385ca6dc64cb1edbc41072d238e8da3ec6f79535))
* automate dau tracking via access log trigger and rolling-average view ([92cf56b](https://github.com/Solierrr/database-console/commit/92cf56b638f591919b4cb968612e44614f5c49c0))
* export postgres tables to parquet for databricks ([f3fe2b5](https://github.com/Solierrr/database-console/commit/f3fe2b52c385e8dca8f878c6a89880eb26bf9546))
* implementing cron-job for aiven &lt;&gt; databricks sync ([6787ec0](https://github.com/Solierrr/database-console/commit/6787ec062a73f169e566133ca7e6e799d30dc409))
* model normalized solaria domain schema in 3nf-5nf ([fc6afa1](https://github.com/Solierrr/database-console/commit/fc6afa184b420e57aaf7ebb51c04a562ce041200))
* scaffold central script runner and per-database connection config ([f6a0e85](https://github.com/Solierrr/database-console/commit/f6a0e851419a958471c3063561ae81e40a7c02b1))
* seed a default free plan for new suppliers ([4d6d07e](https://github.com/Solierrr/database-console/commit/4d6d07ed22c3445c94ec32c2cc4fa059a787c8ed))
* seed baseline permission catalog for management screens ([57d3511](https://github.com/Solierrr/database-console/commit/57d35118d9d079aa0108e07aa2dee9a9f172205a))
* seed permission for viewing another user's basic data ([c133045](https://github.com/Solierrr/database-console/commit/c133045f11d999894c5aee83b086adc06a41ff9a))
* self-bootstrap infra-scripts and split env flow into vault-config, vault-auth, extract-env ([8f0c647](https://github.com/Solierrr/database-console/commit/8f0c6476c789783b3ee00e00e70a7f1a2b1b9971))


### Bug Fixes

* back up selected QA postgres databases ([1e4f8f6](https://github.com/Solierrr/database-console/commit/1e4f8f6fe083431a195d21e277a63675f42587d1))
* correct reset.sql variable substitution and makefile enum/schema order ([#15](https://github.com/Solierrr/database-console/issues/15)) ([a22062c](https://github.com/Solierrr/database-console/commit/a22062c40a9e0576c0829a36ed6bc1313c771111))
* recover dataload rework dropped by the pr [#12](https://github.com/Solierrr/database-console/issues/12) squash merge and align schema with production ([#13](https://github.com/Solierrr/database-console/issues/13)) ([f7fb23e](https://github.com/Solierrr/database-console/commit/f7fb23efa327fd160854a9d810a4301d6264952a))
* register uuid adapter and relax pinned dependency versions ([062bb9e](https://github.com/Solierrr/database-console/commit/062bb9e8fd3c8200df0da9decf6eb0db3f193636))
* support powershell secret extraction ([3b1b800](https://github.com/Solierrr/database-console/commit/3b1b800ca5a6919b40fd50f0352374a909b5cf56))
