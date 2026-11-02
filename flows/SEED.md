<p align="center">
  <img src="../assets/readme/banners/postgresql.png" alt="PostgreSQL" width="100%">
</p>

# Carga planejada

A carga constrói um conjunto determinístico e usa as imagens do catálogo de mocks.

```mermaid
flowchart TD
 A[Plano e manifesto] --> B[Constrói dados e relatório]
 B --> C{Dry run?}
 C -->|sim| D[Encerra sem escrita]
 C -->|não| E[Valida ambiente e imagens]
 E --> F[Grava core e auth]
```

Um ambiente não permitido, uma configuração ausente ou imagens insuficientes no modo estrito interrompem a carga, e em QA a carga exige um hash de senha próprio. A opção `--core-only` evita gravar a identidade, e a `--reset` remove apenas os identificadores gerados pelo plano.