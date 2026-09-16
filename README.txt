Agroanalytica NDVI (NDVI DatVeg)
Este repositório contém um plugin para o QGIS desenvolvido para facilitar a extração e o processamento de séries temporais de vegetação. 
A ferramenta utiliza a integração com a plataforma Satveg para obter dados de índices de vegetação de forma automatizada.

!!!!!IMPORTANTE!!!!!! 
Configuração de Acesso
Para que o plugin funcione, o usuário precisa obrigatoriamente CRIAR UMA CONTA/API para acessar a plataforma Satveg. 
Após obter as credenciais, é necessário abrir o arquivo config.py dentro da pasta do plugin e ATUALIZAR AS INFORMAÇÕES DE ACESSO.

FUNCIONALIDADES

Conexão Satveg: 
Interface direta para busca de dados de séries temporais.

Visualização: 
- Ferramentas para análise de perfis temporais de áreas agrícolas. 
- Faixas de cores para facilitar análise.
- Plota a área que represanta a área de extração do pixel.
- Janela dinâmica com memória de tamanho e último local que esteve.
- Visualização do valor do NDVI e da data de forma dinâmica

Ativação: 
- Ativa ao clicar no ícone da ferramenta.
- Possível de ativar e desativar com a tecla de atalho "n". 
- Também desativa ao clicarmos em outra ferramenta.

INSTALAÇÃO
Baixe este repositório como um arquivo .zip.
No QGIS, vá em Complementos > Gerenciar e Instalar Complementos.
Selecione Instalar a partir de ZIP e aponte para o arquivo baixado.

IMPORTANTE: o arquivo resources.py (gerado a partir de resources.qrc) nao e versionado neste repositorio (ver .gitignore). Antes de empacotar/instalar o plugin, compile-o com: pyrcc5 -o resources.py resources.qrc

DEPENDENCIAS
Alem das bibliotecas ja incluidas no QGIS (PyQt5, qgis.core, qgis.gui), e necessario ter matplotlib, requests e python-dateutil disponiveis no Python usado pelo QGIS (ver requirements.txt).

ESTRUTURA DO PROJETO
Satveg/: Módulos de integração com a plataforma.
NDVI_DATVeg.py: Lógica principal do plugin.
resources.qrc: Arquivos de ícones e recursos visuais.
config.py: Local onde está as credenciais de API a serem atualizadas

DESENVOLVEDORAS
Poliana Cursino Betella
Eliandra Pereira da Silva
