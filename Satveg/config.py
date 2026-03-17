# Satveg/config.py
"""
    CONFIGURATION
"""
CLIENT_ID = "  "  # Use suas credenciais de produção
CLIENT_SECRET = "  " # Use suas credenciais de produção
TOKEN_URL = "https://api.cnptia.embrapa.br/token"

# URL base para o endpoint de séries temporais da API SATVeg v2
# De acordo com a especificação OpenAPI, o caminho é /series e o método é POST
SATVEG_API_SERIES_URL = "https://api.cnptia.embrapa.br/satveg/v2/series"

# Parâmetros padrão para o corpo JSON da requisição POST (Schema: SerieFilterPonto)
# A latitude e longitude serão adicionadas dinamicamente.
# Ajuste estes valores conforme necessário ou torne-os mais configuráveis se precisar variar.
SERIE_FILTER_DEFAULTS = {
    "tipoPerfil": "ndvi",    # Obrigatório: "ndvi" ou "evi"
    "satelite": "comb",      # Obrigatório: "terra", "aqua", ou "comb"
    "preFiltro": 3,          # Opcional: 0 (sem), 1 (nodata), 2 (nuvem), 3 (nuvem/nodata). Use None para omitir.
    "filtro": "sav",         # Opcional: "flt", "wav", "sav". Use None para omitir.
    "parametroFiltro": 4     # Obrigatório se filtro for "flt" ou "sav".
                             # Para "sav": 2, 3, 4, 5, ou 6.
                             # Para "flt": 0, 10, 20, ou 30.
                             # Omitir (ou None) se filtro for "wav" ou se nenhum filtro for usado.
}

# Mapeamento para as chaves da resposta da API
NAME_MAPPING = {
    "listaSerie": "ndvi",
    "listaDatas": "date"
}

# Cabeçalhos padrão para as chamadas à API de dados
DEFAULT_API_HEADERS = {
    "accept": "application/json",
    "Content-Type": "application/json"  # Importante para requisições POST com corpo JSON
}