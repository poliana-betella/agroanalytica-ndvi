# Satveg/core.py
import json
import requests
import datetime
import dateutil.parser
import base64 
import logging

from . import config 
from qgis.core import QgsMessageLog, Qgis # Importando diretamente para uso no logging

# Configuração do logger compatível com QGIS (como você já tinha)
class QGISLogHandler(logging.Handler):
    def emit(self, record):
        try:
            msg = self.format(record)
            level = record.levelno
            if level >= logging.CRITICAL:
                qgis_level = Qgis.Critical
            elif level >= logging.ERROR: # Adicionado para mapear ERROR para Critical também
                qgis_level = Qgis.Critical
            elif level >= logging.WARNING:
                qgis_level = Qgis.Warning
            else: # INFO e DEBUG
                qgis_level = Qgis.Info
            QgsMessageLog.logMessage(msg, "NdviSatveg", qgis_level) # Tag consistente com seu plugin
        except Exception:
            # Em caso de falha ao logar com QgsMessageLog, não fazer nada para evitar loop de erro
            pass

logger = logging.getLogger(__name__) # ex: ndvi_datveg.Satveg.core
logger.setLevel(logging.DEBUG) # Define o nível do logger

# Limpa handlers existentes para evitar duplicação em recarregamentos do plugin
if logger.hasHandlers():
    logger.handlers.clear()

qgis_handler = QGISLogHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
qgis_handler.setFormatter(formatter)
logger.addHandler(qgis_handler)
logger.propagate = False # Não propaga para o logger root, evitando logs duplicados


_cached_token = None
_token_expiry_time = None 

def _get_new_token():
    global _cached_token, _token_expiry_time

    if not config.CLIENT_ID or not config.CLIENT_SECRET:
        logger.critical("CLIENT_ID ou CLIENT_SECRET não configurados em Satveg/config.py.")
        return None

    auth_str = f"{config.CLIENT_ID}:{config.CLIENT_SECRET}"
    auth_b64 = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")

    headers = {
        "Authorization": f"Basic {auth_b64}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data_payload = {"grant_type": "client_credentials"}

    try:
        logger.info(f"Requisitando novo token de: {config.TOKEN_URL}")
        response = requests.post(config.TOKEN_URL, headers=headers, data=data_payload, timeout=30)
        response.raise_for_status()
        token_data_response = response.json()

        _cached_token = token_data_response.get("access_token")
        expires_in_raw = token_data_response.get("expires_in")

        if _cached_token is None:
            logger.error("Token de acesso não encontrado na resposta da API.")
            return None

        expires_in_seconds = 3600 # Padrão
        if expires_in_raw is not None:
            try:
                expires_in_seconds = int(expires_in_raw)
            except (ValueError, TypeError):
                logger.warning(f"Valor de 'expires_in' inválido recebido da API: {expires_in_raw}. Usando padrão de 3600s.")
        
        MAX_EXPIRES = 30 * 24 * 3600 # 30 dias
        if expires_in_seconds > MAX_EXPIRES:
            logger.warning(f"expires_in ({expires_in_seconds}s) excede o máximo configurado ({MAX_EXPIRES}s). Usando o máximo.")
            expires_in_seconds = MAX_EXPIRES
        elif expires_in_seconds < 0:
             logger.warning(f"expires_in ({expires_in_seconds}s) é negativo. Usando 60s como mínimo.")
             expires_in_seconds = 60


        buffer_seconds = 300 # 5 minutos de margem
        safe_timedelta_seconds = max(1, expires_in_seconds - buffer_seconds) # Garante pelo menos 1s de validade efetiva

        _token_expiry_time = datetime.datetime.now() + datetime.timedelta(seconds=safe_timedelta_seconds)
        logger.info(f"Token obtido. expires_in processado: {expires_in_seconds}s. Token expira aproximadamente em: {_token_expiry_time}")
        return _cached_token

    except requests.exceptions.HTTPError as e:
        logger.error(f"Erro HTTP ao obter token: {e.response.status_code} - {e.response.reason}")
        if hasattr(e.response, 'text'): logger.error(f"Detalhes: {e.response.text}")
        return None
    except Exception as e:
        logger.error(f"Erro inesperado ao obter token: {str(e)} (Tipo: {type(e).__name__})")
        return None

def _get_valid_token():
    if _cached_token and _token_expiry_time and datetime.datetime.now() < _token_expiry_time:
        logger.info("Usando token do cache.")
        return _cached_token
    logger.info("Token expirado ou não existente. Obtendo novo token.")
    return _get_new_token()

def _get_timeseries(latitude, longitude):
    token = _get_valid_token()
    if not token:
        logger.critical("Token inválido ou não obtido. Abortando requisição de séries temporais.")
        return {}

    url = config.SATVEG_API_SERIES_URL # Endpoint /series para POST

    # Monta o corpo JSON (payload) da requisição
    payload = {
        "tipoPerfil": config.SERIE_FILTER_DEFAULTS.get("tipoPerfil"),
        "satelite": config.SERIE_FILTER_DEFAULTS.get("satelite"),
        "longitude": longitude,
        "latitude": latitude
    }

    # Adiciona parâmetros opcionais se estiverem definidos em config.py e não forem None
    if config.SERIE_FILTER_DEFAULTS.get("preFiltro") is not None:
        payload["preFiltro"] = config.SERIE_FILTER_DEFAULTS["preFiltro"]
    
    current_filter = config.SERIE_FILTER_DEFAULTS.get("filtro")
    if current_filter:
        payload["filtro"] = current_filter
        parametro_filtro_config = config.SERIE_FILTER_DEFAULTS.get("parametroFiltro")
        if current_filter in ["sav", "flt"]:
            if parametro_filtro_config is not None:
                payload["parametroFiltro"] = parametro_filtro_config
            else:
                logger.warning(f"Filtro '{current_filter}' requer 'parametroFiltro', mas não foi configurado em SERIE_FILTER_DEFAULTS. O filtro pode não funcionar como esperado.")
        # Para 'wav', parametroFiltro não é usado/obrigatório. Se estiver em payload por engano, é ignorado pela API ou pode causar erro se API for estrita.
        # A especificação OpenAPI para SerieFilterPonto não marca parametroFiltro como obrigatório para 'wav'.

    headers = {
        "accept": config.DEFAULT_API_HEADERS.get("accept"),
        "Content-Type": config.DEFAULT_API_HEADERS.get("Content-Type"),
        "Authorization": f"Bearer {token}"
    }

    logger.info(f"Fazendo POST para URL: {url}")
    logger.info(f"Payload (corpo JSON): {json.dumps(payload, indent=2)}") # Loga o payload

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60) # USA POST e json=payload
        response.raise_for_status() # Verifica erros HTTP (4xx, 5xx)
        
        data_response = response.json()
        logger.info("Resposta da API recebida (status 200 OK):")
        logger.info(json.dumps(data_response, indent=2)) # Loga a resposta completa

        if not data_response:
            logger.warning("Resposta da API foi OK, mas o corpo JSON está vazio.")
            return {}

        new_data = {}
        for key, new_key in config.NAME_MAPPING.items():
            if key in data_response:
                new_data[new_key] = data_response[key]
            else:
                logger.warning(f"Chave esperada '{key}' (mapeada para '{new_key}') não encontrada na resposta da API.")
        
        if "date" in new_data and new_data["date"]:
            try:
                new_data["date"] = [dateutil.parser.parse(d).date() for d in new_data["date"]]
            except Exception as e:
                logger.error(f"Erro ao parsear datas da API: {e}. Datas originais: {new_data['date']}")
                # Considerar retornar {} ou tratar como erro fatal se as datas são cruciais
        
        if not new_data.get("ndvi") or not new_data.get("date"): # Checa se ndvi e date existem e não são vazios
            logger.warning("Dados de NDVI ou datas ausentes, vazias ou não mapeadas corretamente na resposta da API.")
            return {}

        return new_data

    except requests.exceptions.HTTPError as e:
        logger.error(f"Erro HTTP ao buscar série temporal: {e.response.status_code} - {e.response.reason}")
        if hasattr(e.response, 'text'): 
            logger.error(f"Detalhes do erro HTTP: {e.response.text}")
            # A especificação OpenAPI indica que erros 400 retornam um JSON com detalhes
            try:
                error_details = e.response.json()
                logger.error(f"Detalhes do erro JSON da API: {json.dumps(error_details, indent=2)}")
            except json.JSONDecodeError:
                pass # O corpo do erro não era JSON válido
        if e.response.status_code in [401, 403]:
            logger.info("Token pode ser inválido ou não autorizado. Forçando renovação na próxima chamada.")
            global _cached_token
            _cached_token = None 
        return {} 
    except requests.exceptions.RequestException as e: 
        logger.error(f"Erro de requisição (ex: timeout, DNS) ao buscar série temporal para URL {url}: {e}")
        return {}
    except Exception as e: 
        logger.error(f"Erro inesperado ao processar dados da série temporal para URL {url}: {str(e)} (Tipo: {type(e).__name__})")
        return {}

# Funções públicas (não alteradas)
def get_timeseries(latitude, longitude):
    return _get_timeseries(latitude, longitude)

# Funções get_timeseries_from_point_dataframe, get_timeseries_dataframe, get_and_plot_timeseries
# foram mantidas como no seu último core.py, mas não são usadas pelo plugin NDVI_DATVeg.py
# ... (elas podem ser removidas se você tiver certeza que não precisa delas)