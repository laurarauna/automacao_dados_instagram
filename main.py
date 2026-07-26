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

def remover_acentos(texto):
    texto_normalizado = unicodedata.normalize('NFD', texto)
    return ''.join(c for c in texto_normalizado if unicodedata.category(c) != 'Mn')

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
    ha_30_dias = hoje - timedelta(days=29) # 29 dias evita conflito de fuso horário na Meta
    
    unix_hoje = int(hoje.timestamp())
    unix_30_dias = int(ha_30_dias.timestamp())

    # Preenchendo com zeros para evitar células em branco se a Meta oscilar
    dados_finais = {
        'Data': hoje.strftime("%Y-%m-%d"), 'Seguidores': 0, 'Crescimento_30d': 0,
        '%_Mulheres': 0, '%_Homens': 0, '%_Norte': 0, '%_Nordeste': 0,
        '%_Centro-Oeste': 0, '%_Sudeste': 0, '%_Sul': 0, '%_Outros': 0,
        'Impressoes_30d': 0, 'Taxa_Engajamento_%': 0, 'Media_Alcance_Post': 0
    }

    # 1. Seguidores Totais
    req_seguidores = requests.get(f"{base_url}/{IG_ID}?fields=followers_count&access_token={META_TOKEN}").json()
    seguidores_atuais = req_seguidores.get('followers_count', 0)
    dados_finais['Seguidores'] = seguidores_atuais

    # 2. Histórico de Seguidores (Crescimento) - Chamada Isolada
    req_hist = requests.get(f"{base_url}/{IG_ID}/insights?metric=follower_count&period=day&since={unix_30_dias}&until={unix_hoje}&access_token={META_TOKEN}").json()
    if 'data' in req_hist:
        for insight in req_hist['data']:
            if insight['name'] == 'follower_count' and len(insight['values']) > 0:
                dados_finais['Crescimento_30d'] = insight['values'][-1]['value'] - insight['values'][0]['value']

    # 3. Demografia (Lifetime) - Chamada Isolada sem Data Limitadora
    req_demo = requests.get(f"{base_url}/{IG_ID}/insights?metric=audience_gender_age,audience_city&period=lifetime&access_token={META_TOKEN}").json()
    if 'data' in req_demo:
        for insight in req_demo['data']:
            if insight['name'] == 'audience_gender_age':
                demografia = insight['values'][0]['value']
                total_genero = sum(demografia.values())
                mulheres = sum(v for k, v in demografia.items() if k.startswith('F'))
                homens = sum(v for k, v in demografia.items() if k.startswith('M'))
                dados_finais['%_Mulheres'] = round((mulheres / total_genero) * 100, 2) if total_genero else 0
                dados_finais['%_Homens'] = round((homens / total_genero) * 100, 2) if total_genero else 0
                
            elif insight['name'] == 'audience_city':
                cidades = insight['values'][0]['value']
                total_cidades = sum(cidades.values())
                contagem_regioes = {'Norte': 0, 'Nordeste': 0, 'Centro-Oeste': 0, 'Sudeste': 0, 'Sul': 0, 'Outros': 0}
                
                for cidade_string, quantidade in cidades.items():
                    partes = cidade_string.split(', ')
                    if len(partes) > 1:
                        estado_limpo = remover_acentos(partes[1].lower().strip())
                        regiao_encontrada = 'Outros'
                        for regiao, estados in REGIOES_BR.items():
                            if estado_limpo in estados:
                                regiao_encontrada = regiao
                                break
                        contagem_regioes[regiao_encontrada] += quantidade
                    else:
                        contagem_regioes['Outros'] += quantidade
                
                for regiao, qtd in contagem_regioes.items():
                    dados_finais[f'%_{regiao}'] = round((qtd / total_cidades) * 100, 2) if total_cidades else 0

    # 4. Impressões (Últimos 30 dias) - Chamada Isolada
    req_impressoes = requests.get(f"{base_url}/{IG_ID}/insights?metric=impressions&period=day&since={unix_30_dias}&until={unix_hoje}&access_token={META_TOKEN}").json()
    if 'data' in req_impressoes:
        total_impressoes = sum(v['value'] for item in req_impressoes['data'] for v in item.get('values', []))
        dados_finais['Impressoes_30d'] = total_impressoes

    # 5. Mídia Recente (Para Alcance e Engajamento)
    req_media = requests.get(f"{base_url}/{IG_ID}/media?fields=like_count,comments_count,insights.metric(reach)&limit=30&access_token={META_TOKEN}").json()
    
    if 'data' in req_media:
        posts = req_media['data']
        total_alcance = 0
        total_interacoes = 0

        for post in posts:
            total_interacoes += post.get('like_count', 0) + post.get('comments_count', 0)
            insights_post = post.get('insights', {}).get('data', [])
            for p_insight in insights_post:
                if p_insight['name'] == 'reach':
                    total_alcance += p_insight['values'][0]['value']

        qtd_posts = len(posts)
        if qtd_posts > 0:
            dados_finais['Media_Alcance_Post'] = round(total_alcance / qtd_posts)
            
            # CORREÇÃO: (Média de interações por post / Seguidores) * 100
            media_interacoes_post = total_interacoes / qtd_posts
            dados_finais['Taxa_Engajamento_%'] = round((media_interacoes_post / seguidores_atuais) * 100, 2) if seguidores_atuais else 0

    return dados_finais

def salvar_no_sheets(dados):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credenciais_dict = json.loads(GOOGLE_JSON_STR)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(credenciais_dict, scope)
    client = gspread.authorize(creds)
    
    sheet = client.open_by_key(SHEET_ID).sheet1
    
    linha = [
        dados.get('Data'), dados.get('Seguidores'), dados.get('Crescimento_30d'),
        dados.get('%_Mulheres'), dados.get('%_Homens'), dados.get('%_Norte'),
        dados.get('%_Nordeste'), dados.get('%_Centro-Oeste'), dados.get('%_Sudeste'),
        dados.get('%_Sul'), dados.get('%_Outros'), dados.get('Impressoes_30d'),
        dados.get('Taxa_Engajamento_%'), dados.get('Media_Alcance_Post')
    ]
    
    sheet.append_row(linha)
    print("Dados inseridos com sucesso!")

if __name__ == "__main__":
    print("Iniciando extração do Mídia Kit...")
    metricas = get_instagram_data()
    print("Dados extraídos:", metricas)
    salvar_no_sheets(metricas)
