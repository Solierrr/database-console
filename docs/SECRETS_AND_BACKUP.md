<p align="center">
  <img src="../assets/readme/banners/postgresql.png" alt="PostgreSQL" width="100%">
</p>

# Credenciais e backup

O `make vault` obtém a configuração da pasta `/database` no Infisical e grava o `.env`, que é ignorado pelo Git, e os comandos usam apenas os nomes das variáveis, sem que nenhum valor precise aparecer na documentação.

Os comandos `make backup TARGET=core`, `TARGET=auth` ou `TARGET=all` chamam o script PowerShell com o `pg_dump`, gerando um dump em SQL plain. A gravação usa um arquivo temporário, que só recebe o nome final depois de terminar com sucesso e com conteúdo, e os arquivos ficam em `backups/`, fora do versionamento, sem incluir o MongoDB nem o banco de analytics.

O backup é diário, guardado fora do repositório. Os dumps podem conter dados das contas e precisam permanecer fora do repositório.

O contrato em `db/roles/contracts.json` separa grupos sem login e logins por consumidor. O comando `roles.py login` obtém a senha de uma variável de ambiente indicada pelo operador. Os papéis de leitura não recebem acesso geral a `public`.
