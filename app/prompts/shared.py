"""Componentes compartilhados pelas estratégias de prompting.

Regra experimental fundamental: as três estratégias (zero-shot, few-shot,
chain-of-thought) compartilham **a mesma tarefa, o mesmo contexto, as mesmas
informações financeiras, as mesmas restrições e o mesmo formato de resposta**.
A única variável manipulada é a técnica de prompting.

Por isso, os blocos abaixo são definidos uma única vez e reutilizados por todas
as estratégias. Manter uma fonte única evita divergências acidentais que
invalidariam a comparação.
"""

from __future__ import annotations

# Instruções permanentes do agente financeiro (base compartilhada).
# É a mesma base usada pelo agente LangChain (ver app.agents).
BASE_AGENT_INSTRUCTIONS = (
    "Você é um assistente especializado em análise de dados financeiros.\n"
    "Utilize ferramentas sempre que a pergunta depender de dados financeiros.\n"
    "Nunca invente valores de mercado.\n"
    "Se os dados necessários não estiverem disponíveis, informe explicitamente a "
    "limitação.\n"
    "Diferencie fatos obtidos pelas ferramentas de interpretação realizada pelo "
    "modelo.\n"
    "Não apresente a resposta como recomendação personalizada de investimento e "
    "não forneça indicação de compra ou venda."
)

# Restrições compartilhadas por TODAS as estratégias (idênticas).
SHARED_CONSTRAINTS = (
    "Restrições (válidas para qualquer resposta):\n"
    "1. Baseie-se apenas em dados obtidos por ferramentas ou explicitamente "
    "fornecidos no contexto. Não invente preços, datas ou valores.\n"
    "2. Se um dado necessário não estiver disponível, declare a limitação em vez "
    "de estimar.\n"
    "3. Separe claramente fatos (obtidos dos dados) de interpretações do modelo.\n"
    "4. Não faça recomendação de compra, venda ou investimento."
)

# Formato de resposta compartilhado por TODAS as estratégias (idêntico).
# A resposta persistida para análise contém: resposta final, justificativa
# concisa e dados utilizados.
RESPONSE_FORMAT = (
    "Formato obrigatório da resposta (use exatamente estes rótulos):\n"
    "Resposta final: <conclusão direta e objetiva>\n"
    "Justificativa: <justificativa concisa do resultado>\n"
    "Dados utilizados: <dados que fundamentaram a resposta, com valor, data, "
    "moeda e fonte>"
)

# Exemplos usados SOMENTE pela estratégia few-shot. Empregam ativos fictícios,
# distintos de qualquer problema real, para manter os exemplos separados do
# problema avaliado.
FEW_SHOT_EXAMPLES = (
    "Exemplos ilustrativos (entrada → saída). Servem apenas de referência de "
    "formato e raciocínio; NÃO são os dados do problema atual:\n"
    "\n"
    "[Exemplo 1]\n"
    "Tarefa: Qual foi o retorno da XYZ3.SA entre 2023-01-02 e 2023-06-01?\n"
    "Dados: XYZ3.SA fechou a 10,00 BRL em 2023-01-02 e a 12,00 BRL em 2023-06-01 "
    "(fonte: snapshot).\n"
    "Resposta final: +20,0%.\n"
    "Justificativa: (12,00 / 10,00 − 1) × 100 = 20,0%.\n"
    "Dados utilizados: XYZ3.SA — fechamento 10,00 BRL (2023-01-02) e 12,00 BRL "
    "(2023-06-01), fonte snapshot.\n"
    "\n"
    "[Exemplo 2]\n"
    "Tarefa: Qual é a cotação atual da ABC4.SA?\n"
    "Dados: ABC4.SA a 25,50 BRL em 2023-06-01 (fonte: snapshot).\n"
    "Resposta final: 25,50 BRL.\n"
    "Justificativa: cotação obtida diretamente da fonte de dados.\n"
    "Dados utilizados: ABC4.SA — 25,50 BRL, 2023-06-01, fonte snapshot."
)

# Instruções de raciocínio estruturado usadas SOMENTE pela estratégia
# chain-of-thought. Pede decomposição antes da conclusão, sem exigir a exposição
# de raciocínio privado completo.
CHAIN_OF_THOUGHT_INSTRUCTIONS = (
    "Antes de concluir, decomponha o problema de forma estruturada:\n"
    "1. Identifique exatamente o que a pergunta requer.\n"
    "2. Liste quais dados financeiros são necessários e quais foram obtidos.\n"
    "3. Realize os cálculos ou a análise passo a passo com base nesses dados.\n"
    "4. Verifique a coerência do resultado.\n"
    "Não é necessário expor todo o raciocínio intermediário: apresente uma "
    "justificativa concisa que reflita os passos essenciais e, então, a resposta "
    "final no formato exigido."
)
