<p align="center">
  <img src="../assets/readme/banners/postgresql.png" alt="PostgreSQL" width="100%">
</p>

# Cópia PostgreSQL

O operador escolhe core, auth ou ambos e inicia o dump.

```mermaid
flowchart TD
 A[Seleciona banco e configuração] --> B[Valida variáveis e pg_dump]
 B --> C[Grava arquivo temporário]
 C --> D{Processo terminou com conteúdo?}
 D -->|não| E[Remove temporário e informa erro]
 D -->|sim| F[Publica arquivo SQL com data]
```

Configuração incompleta, executável ausente, erro no dump e arquivo vazio impedem a publicação do backup. Um arquivo final existente não é sobrescrito.
