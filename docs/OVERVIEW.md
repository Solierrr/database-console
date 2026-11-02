<p align="center">
  <img src="../assets/readme/banners/postgresql.png" alt="PostgreSQL" width="100%">
</p>

# Visão de produto

A equipe usa os utilitários para preparar dados de desenvolvimento, manter acessos por consumidor e salvar cópias dos bancos. O repositório também prepara o destino dos indicadores calculados pela plataforma.

O carregamento planejado cria empresas, profissionais, ofertas, projetos e pedidos para o trabalho de desenvolvimento. Repetir a carga não deve duplicar os identificadores do plano. A carga de QA exige configuração própria, e a carga completa não é permitida em produção.

O acesso direto aos dados é definido por consumidor e pelo menor conjunto de permissões previsto no contrato, e os indicadores de fornecedores, demandantes e profissionais são separados por identidade e escopo. O backup dos bancos é diário.
