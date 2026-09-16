# Changelog

Todas as mudancas notaveis deste projeto serao documentadas neste arquivo.

O formato e baseado em Keep a Changelog (https://keepachangelog.com/pt-BR/1.0.0/), e este projeto adere ao Versionamento Semantico (https://semver.org/lang/pt-BR/).

## [1.0.0] - 2026-03-17

### Adicionado

Plugin QGIS "NDVI-SATVeg": obtencao interativa de curvas NDVI a partir da plataforma SATVeg (Embrapa), clicando diretamente no mapa.

Visualizacao grafica interativa (matplotlib) com tooltip de valor/data ao passar o mouse sobre a curva.

Identificacao automatica do municipio do ponto clicado via camada local de municipios (IBGE).

Script auxiliar plugin_upload.py para publicacao no repositorio oficial de plugins do QGIS.

### Corrigido

Removida chamada orfa a standard_library.install_aliases() em plugin_upload.py (resquicio de compatibilidade Python 2/3 sem o import correspondente), que impedia a execucao do script.
