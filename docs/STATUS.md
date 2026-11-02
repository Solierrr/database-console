<p align="center">
  <img src="../assets/readme/banners/postgresql.png" alt="PostgreSQL" width="100%">
</p>

# Situação

Leitura da main em 2026-10-31.

- Não há mais DDL de negócio e identidade aqui. As APIs são donas de seus schemas.
- O schema de analytics cria controle de autorização. As tabelas de indicadores são criadas pelo exportador conforme as views publicadas.
- `ro_bootstrap` lê objetos selecionados de `export`. `ro_databricks` lê as views de `export` nos dois bancos. `rpa_writer` escreve apenas nos objetos contratados e somente em QA.
- `ro_mcp` e `ro_recommendation` foram removidos do contrato, e os consumidores que ainda usam acesso SQL direto precisam migrar.
- A classificação do diretório de backup procura `Environment=` no cabeçalho, enquanto `make vault` escreve `env=`. O diretório pode ser classificado como `unknown`.
- O backup é diário, e os exercícios de restauração não estão automatizados.
