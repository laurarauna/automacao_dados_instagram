import os
import json
import requests
import gspread
import unicodedata
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta

# Variáveis de Ambiente
META_TOKEN = os.environ.get("META_TOKEN")
IG_ID = os.environ.get("IG_ID")
SHEET_ID = os.environ.get("SHEET_ID")
GOOGLE_JSON_STR = os.environ.get("GOOGLE_JSON")

# Função para limpar acentos (Ex: "Goiás" vira "goias")
def remover_acentos(texto):
    texto_normalizado = unicodedata.normalize('NFD', texto)
    return ''.join(c for c in texto_normalizado if unicodedata.category(c) != 'Mn')

# Mapeamento oficial das regiões do Brasil
REGIOES_BR = {
    'Norte': ['acre', 'amapa', 'amazonas', 'para', 'rondonia', 'roraima', 'tocantins'],
    'Nordeste': ['alagoas', 'bahia', 'ceara', 'maranhao', 'paraiba', 'pernambuco', 'piaui', 'rio grande do norte', 'sergipe'],
    'Centro-Oeste': ['goias', 'mato grosso', 'mato grosso do sul', 'distrito federal'],
    'Sudeste': ['espirito santo', 'minas gerais', 'rio de janeiro', 'sao paulo'],
    'Sul': ['parana', 'rio grande do sul', 'santa catarina']
}

def get_instagram_data():
    base_url = "https://graph.facebook.com/v19.0"
    hoje = datetime.now()
    ha_30_dias = hoje - timedelta(days=30)
    
    unix_hoje = int(hoje.timestamp())
    unix_30_dias = int(ha_30_dias.timestamp())

    dados_finais = {"Data": hoje.strftime("%Y-%m-%d")}

    # 1. Seguidores Totais
    req_seguidores = requests.get(f"{base_url}/{IG_ID}?fields=followers_count&access_token={META_TOKEN}").json()
    seguidores_atuais = req_seguidores.get('followers_count', 0)
    dados_finais['Seguidores'] = seguidores_atuais

    # 2. Histórico e Demografia
    req_insights = requests.get(
        f"{base_url}/{IG_ID}/insights?metric=follower_count,audience_gender_age,audience_city&period=day,lifetime&since={unix_30_dias}&until={unix_hoje}&access_token={META_TOKEN}"
    ).json()

    for insight in req_insights.get('data', []):
        if insight['name'] == 'follower_count':
            valores = insight['values']
            if len(valores) > 0:
                crescimento = valores[-1]['value'] - valores[0]['value']
                dados_finais['Crescimento_30d'] = crescimento
        
        elif insight['name'] == 'audience_gender_age':
            demografia = insight['values'][0]['value']
            total_genero = sum(demografia.values())
            mulheres = sum(v for k, v in demografia.items() if k.startswith('F'))
            homens = sum(v for k, v in demografia.items() if k.startswith('M'))
            dados_finais['%_Mulheres'] = round((mulheres / total_genero) * 100, 2) if total_genero else 0
            dados_finais['%_Homens'] = round((homens / total_genero) * 100, 2) if total_genero else 0
            
        elif insight['name'] == 'audience_city':
            cidades = insight['values'][0]['value']
            total_cidades = sum(cidades.values())
            
            # Zerando os contadores de regiões
            contagem_regioes = {'Norte': 0, 'Nordeste': 0, 'Centro-Oeste': 0, 'Sudeste': 0, 'Sul': 0, 'Outros': 0}
            
            for cidade_string, quantidade in cidades.items():
                partes = cidade_string.split(', ')
                if len(partes) > 1:
                    estado_limpo = remover_acentos(partes[1].lower().strip())
                    regiao_encontrada = 'Outros'
                    
                    # Procura o estado no nosso dicionário
                    for regiao, estados in REGIOES_BR.items():
                        if estado_limpo in estados:
                            regiao_encontrada = regiao
                            break
                            
                    contagem_regioes[regiao_encontrada] += quantidade
                else:
                    contagem_regioes['Outros'] += quantidade
            
            # Calculando a porcentagem final de cada região
            for regiao, qtd in contagem_regioes.items():
                dados_finais[f'%_{regiao}'] = round((qtd / total_cidades) * 100, 2) if total_cidades else 0

    # 3. Impressões (Últimos 30 dias)
    req_impressoes = requests.get(
        f"{base_url}/{IG_ID}/insights?metric=impressions&period=day&since={unix_30_dias}&until={unix_hoje}&access_token={META_TOKEN}"
    ).json()
    
    total_impressoes = sum(v['value'] for item in req_impressoes.get('data', []) for v in item.get('values', []))
    dados_finais['Impressoes_30d'] = total_impressoes

    # 4. Mídia Recente (Para Alcance e Engajamento)
    req_media = requests.get(
        f"{base_url}/{IG_ID}/media?fields=like_count,comments_count,insights.metric(reach)&limit=30&access_token={META_TOKEN}"
    ).json()

    posts = req_media.get('data', [])
    total_alcance = 0
    total_interacoes = 0

    for post in posts:
        total_interacoes += post.get('like_count', 0) + post.get('comments_count', 0)
        insights_post = post.get('insights', {}).get('data', [])
        for p_insight in insights_post:
            if p_insight['name'] == 'reach':
                total_alcance += p_insight['values'][0]['value']

    qtd_posts = len(posts)
    dados_finais['Media_Alcance_Post'] = round(total_alcance / qtd_posts) if qtd_posts else 0
    
    # Calculando taxa de engajamento
    dados_finais['Taxa_Engajamento_%'] = round((total_interacoes / seguidores_atuais) * 100, 2) if seguidores_atuais else 0

    return dados_finais

def salvar_no_sheets(dados):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credenciais_dict = json.loads(GOOGLE_JSON_STR)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(credenciais_dict, scope)
    client = gspread.authorize(creds)
    
    sheet = client.open_by_key(SHEET_ID).sheet1
    
    linha = [
        dados.get('Data'),
        dados.get('Seguidores'),
        dados.get('Crescimento_30d'),
        dados.get('%_Mulheres'),
        dados.get('%_Homens'),
        dados.get('%_Norte'),
        dados.get('%_Nordeste'),
        dados.get('%_Centro-Oeste'),
        dados.get('%_Sudeste'),
        dados.get('%_Sul'),
        dados.get('%_Outros'),
        dados.get('Impressoes_30d'),
        dados.get('Taxa_Engajamento_%'),
        dados.get('Media_Alcance_Post')
    ]
    
    sheet.append_row(linha)
    print("Dados inseridos com sucesso!")

if __name__ == "__main__":
    print("Iniciando extração do Mídia Kit...")
    metricas = get_instagram_data()
    print("Dados extraídos:", metricas)
    salvar_no_sheets(metricas)
