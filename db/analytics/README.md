# analyticsdb: destino dos KPIs Gold

`make create TARGET=analytics ENVIRONMENT=prod` cria `analyticsdb` sem apagar
um banco existente. Depois, `make schema TARGET=analytics ENVIRONMENT=prod`
aplica `db/analytics/schema.sql`. Para QA, use `ENVIRONMENT=qa` (`analyticsdbqa`).
Esses comandos não foram executados nesta alteração.

O schema `gold` recebe tabelas com os mesmos nomes e colunas das
19 tabelas do schema `gold` do catálogo `analytics` do Databricks, listadas em
`databricks-sync/gold_export_manifest.json`. O exportador cria essas tabelas
na primeira carga e exige schema idêntico nas seguintes. O DDL não antecipa
tipos que só serão conhecidos após a pipeline publicar cada view. Uma mudança
de estrutura exige migração revisada; o exportador falha sem substituir dados.

`schema.sql` cria apenas o schema, o registro privado
`gold.principal_access` e a função de autorização. A carga aplica
Row Level Security forçado nas tabelas KPI. O registro começa vazio. A equipe
de banco deve cadastrar logins verificados com `scope` `ADMIN`, `EXPORTER`,
`SUPPLIER`, `REQUESTER` ou `PROFESSIONAL`, `entity_id` (identificador da
entidade, ou `*` para ADMIN/EXPORTER), `validated_by` e `validated_at`.
Um login de fornecedor, demandante ou profissional com mais de uma entidade
ativa no mesmo escopo recebe zero linhas daquele escopo.

O login que criou a função pode exportar. Se o login do exportador for outro,
cadastre-o como `EXPORTER`. Use credenciais distintas para consumidores; um
login compartilhado não permite isolamento individual por `session_user`.
Não conceda `BYPASSRLS`, escrita ou propriedade dos objetos a leitores. O
`ANALYTICS_READER_ROLE` opcional do exportador só recebe USAGE, EXECUTE e SELECT;
os logins devem ser associados à role separadamente.

O AnalyticsDB é destino dos KPIs Gold. Ele não fornece a entrada Silver/Gold
para o Databricks neste fluxo.
