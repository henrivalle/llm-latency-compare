# LLM Latency Compare

[English](README.md) · [Como contribuir](CONTRIBUTING.md)

Compare a latência de dois experimentos com as mesmas requisições. Execute a partir da raiz com Python 3.11 ou posterior.

```sh
python3 -m llm_latency_compare examples/baseline.csv examples/candidate.csv \
  --max-p95-regression-ms 30 --max-error-increase-pp 10
```

Cada CSV em UTF-8 tem as colunas `request_id,status,duration_ms,ttft_ms`, com o mesmo conjunto de IDs nos dois arquivos. O `status` é `ok` ou `error`. Deixe `ttft_ms` vazio se o tempo até o primeiro token não foi medido ou a requisição falhou. Compare execuções com a mesma carga e método de medição.

Os percentis p50 e p95 usam apenas pares bem-sucedidos nos dois experimentos. A mudança na taxa de erro inclui todas as tentativas e é dada em pontos percentuais. O exemplo retorna `1` porque há regressão nas duas métricas. Entrada inválida retorna `2`.

O relatório conta as requisições que passaram de sucesso para falha (`newly_failed_requests`) e de falha para sucesso (`recovered_requests`). A taxa de erro pode ficar estável quando uma requisição volta a funcionar e outra começa a falhar. Use `--max-newly-failed-requests 0` para reprovar a comparação quando qualquer requisição que antes funcionava passar a falhar.
