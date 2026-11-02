<p align="center">
  <img src="../assets/readme/banners/postgresql.png" alt="PostgreSQL" width="100%">
</p>

# Preparação de schema

A criação de um banco não substitui as migrations das APIs.

```mermaid
flowchart TD
 A[Seleciona destino] --> B[Cria banco se não existe]
 B --> C{Tipo de banco}
 C -->|Negócio ou identidade| D[Flyway da API dona]
 C -->|Analytics| E[Aplica schema gold]
 D --> F[Schema disponível]
 E --> F
```

Banco inacessível, privilégio insuficiente e migration incompatível interrompem a operação. A criação de analytics não apaga um banco existente.
