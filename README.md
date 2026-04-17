# Painel DCF

Aplicacao Dash multipagina para acompanhamento de execucao orcamentaria, dotacao, pagamentos, passagens e naturezas de despesa da DCF.

## Requisitos

- Python 3.11+
- Dependencias de `requirements.txt`

## Como executar

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

O app sobe por padrao em `http://localhost:8051`.

## Configuracoes uteis

- `PAINEL_CACHE_DIR`: define a pasta raiz de cache em disco.
- `PAINEL_DCF_CACHE_DIR`: sobrescreve especificamente a pasta de cache do DCF.
- `PAINEL_DEFAULT_YEAR`: define o ano padrao usado nas telas que dependem de um ano inicial.

Se nenhuma variavel for informada, o projeto usa:

- cache em uma pasta temporaria do sistema
- ano padrao igual ao ano corrente em `America/Sao_Paulo`

## Estrutura

- [app.py](C:/Users/PRAD130_176/Desktop/Painel_DCF/app.py): inicializacao do Dash e layout principal
- `pages/`: paginas e callbacks do painel
- `assets/`: CSS e imagens
- `utils/`: utilitarios compartilhados de runtime e configuracao

## Melhorias herdadas do Painel DCC

- documentacao inicial do projeto
- `.gitignore` para reduzir ruido de ambiente local
- utilitarios compartilhados para timezone, ano padrao e diretorios de cache
- base preparada para reaproveitar configuracoes comuns entre paginas
