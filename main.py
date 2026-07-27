import os
import json
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta

META_TOKEN = os.environ.get("META_TOKEN")
IG_ID = os.environ.get("IG_ID")
SHEET_ID = os.environ.get("SHEET_ID")
GOOGLE_JSON_STR = os.environ.get("GOOGLE_JSON")

def get_instagram_data():
    base_url = "https://graph.facebook.com/v19.0"
    hoje = datetime.now()
    ha_30_dias = hoje - timedelta(days=29)
    unix_hoje = int(hoje.timestamp())
    unix_30_dias = int(ha_30_dias.timestamp())

    dados_finais = {
        'Data': hoje.strftime("%Y-%m-%d"), 'Seguidores': 0, 'Crescimento_30d': 0,
        '%_Mulheres': 0, '%_Homens': 0, 'Faixa_Etaria': "N/A", 'Top_5_Cidades': "N/A", 
        'Impressoes_30d': 0, 'Media_Alcance_Post': 0, 'Media_Salvos_Post': 0, 
        'Media_Compartilhamentos_Post': 0, 'Taxa_Engajamento_%': 0
    }

    # 1. Seguidores Totais
    try:
        req_seguidores = requests.get(f"{base_url}/{IG_ID}?fields=followers_count&access_token={META_TOKEN}").json()
        dados_finais['Seguidores'] = req_seguidores.get('followers_count', 0)
    except: pass

    # 2. Crescimento
    try:
        req_hist = requests.get(f"{base_url}/{IG_ID}/insights?metric=follower_count&period=day&since={unix_30_dias}&until={unix_hoje}&access_token={META_TOKEN}").json()
        if 'data' in req_hist and len(req_hist['data']) > 0:
            dados_finais['Crescimento_30d'] = sum(v['value'] for v in req_hist['data'][0]['values'])
    except: pass

    # 3. Demografia: Gênero
    try:
        req_demo_gender = requests.get(f"{base_url}/{IG_ID}/insights?metric=follower_demographics&period=lifetime&metric_type=total_value&timeframe=last_30_days&breakdown=gender&access_token={META_TOKEN}").json()
        if 'data' in req_demo_gender and req_demo_gender['data']:
            results = req_demo_gender['data'][0]['total_value']['breakdowns'][0]['results']
            mulheres = sum(r['value'] for r in results if r['dimension_values'][0] == 'F')
            homens = sum(r['value'] for r in results if r['dimension_values'][0] == 'M')
            total_genero = mulheres + homens
            dados_finais['%_Mulheres'] = round((mulheres / total_genero) * 100, 2) if total_genero else 0
            dados_finais['%_Homens'] = round((homens / total_genero) * 100, 2) if total_genero else 0
    except: pass

    # 4. Demografia: Faixa Etária (Top 3)
    try:
        req_demo_age = requests.get(f"{base_url}/{IG_ID}/insights?metric=follower_demographics&period=lifetime&metric_type=total_value&timeframe=last_30_days&breakdown=age&access_token={META_TOKEN}").json()
        if 'data' in req_demo_age and req_demo_age['data']:
            results = req_demo_age['data'][0]['total_value']['breakdowns'][0]['results']
            
            # Ordena as idades da maior para a menor quantidade
            idades_ordenadas = sorted(results, key=lambda x: x['value'], reverse=True)
            top_3 = idades_ordenadas[:3] # Pega apenas as 3 principais
            
            total_seguidores = dados_finais['Seguidores']
            lista_strings_idades = []
            
            for i, idade in enumerate(top_3, 1):
                faixa = idade['dimension_values'][0]
                porcentagem = round((idade['value'] / total_seguidores) * 100, 2) if total_seguidores else 0
                lista_strings_idades.append(f"{i}º {faixa} anos ({porcentagem}%)")
                
            dados_finais['Faixa_Etaria'] = " | ".join(lista_strings_idades)
    except: pass

    # 5. Demografia: Top 5 Cidades
    try:
        req_demo_city = requests.get(f"{base_url}/{IG_ID}/insights?metric=follower_demographics&period=lifetime&metric_type=total_value&timeframe=last_30_days&breakdown=city&access_token={META_TOKEN}").json()
        if 'data' in req_demo_city and req_demo_city['data']:
            results = req_demo_city['data'][0]['total_value']['breakdowns'][0]['results']
            
            cidades_ordenadas = sorted(results, key=lambda x: x['value'], reverse=True)
            top_5 = cidades_ordenadas[:5]
            
            total_seguidores = dados_finais['Seguidores']
            lista_strings_cidades = []
            
            for i, cidade in enumerate(top_5, 1):
                nome = cidade['dimension_values'][0]
                porcentagem = round((cidade['value'] / total_seguidores) * 100, 2) if total_seguidores else 0
                lista_strings_cidades.append(f"{i}º {nome} ({porcentagem}%)")
                
            dados_finais['Top_5_Cidades'] = " | ".join(lista_strings_cidades)
    except: pass

    # 6. Impressões
    try:
        req_impressoes = requests.get(f"{base_url}/{IG_ID}/insights?metric=reach&period=day&since={unix_30_dias}&until={unix_hoje}&access_token={META_TOKEN}").json()
        if 'data' in req_impressoes:
            dados_finais['Impressoes_30d'] = sum(v['value'] for item in req_impressoes['data'] for v in item.get('values', []))
    except: pass

    # 7. Mídia (Salvos e Compartilhamentos)
    try:
        req_media = requests.get(f"{base_url}/{IG_ID}/media?fields=like_count,comments_count,insights.metric(reach,saved,shares)&limit=30&access_token={META_TOKEN}").json()
        if 'data' in req_media:
            posts = req_media['data']
            total_alcance = 0
            total_interacoes = 0
            total_salvos = 0
            total_compartilhamentos = 0
            
            for post in posts:
                total_interacoes += post.get('like_count', 0) + post.get('comments_count', 0)
                
                for p_insight in post.get('insights', {}).get('data', []):
                    if p_insight['name'] == 'reach':
                        total_alcance += p_insight['values'][0]['value']
                    elif p_insight['name'] == 'saved':
                        total_salvos += p_insight['values'][0]['value']
                    elif p_insight['name'] == 'shares':
                        total_compartilhamentos += p_insight['values'][0]['value']

            qtd_posts = len(posts)
            if qtd_posts > 0:
                dados_finais['Media_Alcance_Post'] = round(total_alcance / qtd_posts)
                dados_finais['Media_Salvos_Post'] = round(total_salvos / qtd_posts)
                dados_finais['Media_Compartilhamentos_Post'] = round(total_compartilhamentos / qtd_posts)
                
                media_interacoes = total_interacoes / qtd_posts
                dados_finais['Taxa_Engajamento_%'] = round((media_interacoes / dados_finais['Seguidores']) * 100, 2) if dados_finais['Seguidores'] else 0
    except: pass

    return dados_finais

def salvar_no_sheets(dados):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credenciais_dict = json.loads(GOOGLE_JSON_STR)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(credenciais_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).sheet1
    
    linha = [
        dados.get('Data'), dados.get('Seguidores'), dados.get('Crescimento_30d'),
        dados.get('%_Mulheres'), dados.get('%_Homens'), dados.get('Faixa_Etaria'), 
        dados.get('Top_5_Cidades'), dados.get('Impressoes_30d'), dados.get('Media_Alcance_Post'), 
        dados.get('Media_Salvos_Post'), dados.get('Media_Compartilhamentos_Post'), 
        dados.get('Taxa_Engajamento_%')
    ]
    
    sheet.append_row(linha)
    print("Dados inseridos com sucesso!")

if __name__ == "__main__":
    print("Iniciando extração do Mídia Kit...")
    metricas = get_instagram_data()
    print("Dados extraídos:", metricas)
    salvar_no_sheets(metricas)
