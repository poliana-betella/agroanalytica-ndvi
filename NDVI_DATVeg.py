# -*- coding: utf-8 -*-
"""
/***************************************************************************
 NdviSatveg
                                 A QGIS plugin
 Gera uma curva NDVI para a área de interesse (clicando no mapa)
                              -------------------
        begin                : 2025-05-28
        copyright            : (C) 2025 by Eliandra Silva e Poliana Betella
 ***************************************************************************/
"""
# Importações do QGIS e PyQt
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt, QLocale
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.PyQt.QtWidgets import QAction, QToolBar
from qgis.core import (
    QgsProject,
    QgsPointXY,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsMessageLog,
    Qgis,
    QgsGeometry,
    QgsVectorLayer,
    QgsFeatureRequest
)
from qgis.gui import QgsMapTool, QgsMapToolEmitPoint, QgsMessageBar, QgsRubberBand

# Importações Padrão e de Terceiros
import os.path
import datetime
import math

# --- Lógica e Dependências da biblioteca Satveg ---
try:
    from .Satveg import core as satveg_core
    SATVEG_LIB_AVAILABLE = True
except ImportError as e:
    SATVEG_LIB_AVAILABLE = False
    QgsMessageLog.logMessage(f"AVISO: Biblioteca local 'Satveg' não encontrada ou erro na importação: {e}. A busca de dados não funcionará.", "NdviSatveg Plugin", Qgis.Critical)

# --- Lógica e Dependências Matplotlib ---
try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    QgsMessageLog.logMessage("AVISO: Biblioteca 'matplotlib' não encontrada. A exibição de gráficos não funcionará.", "NdviSatveg Plugin", Qgis.Warning)

from .NDVI_DATVeg_dockwidget import NdviSatvegDockWidget
from .resources import *

class PointTool(QgsMapToolEmitPoint):
    def __init__(self, canvas, plugin_action):
        self.canvas = canvas
        self.plugin_action = plugin_action
        QgsMapToolEmitPoint.__init__(self, self.canvas)
        self.crs_wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")

    def canvasPressEvent(self, e):
        if not SATVEG_LIB_AVAILABLE or not MATPLOTLIB_AVAILABLE:
            level = Qgis.Critical
            title = self.plugin_action.tr("Erro de Dependência")
            message = self.plugin_action.tr("Biblioteca 'Satveg' ou 'matplotlib' não está instalada corretamente. Verifique os logs.")
            self.plugin_action.iface.messageBar().pushMessage(title, message, level=level, duration=10)
            return

        point_map = self.toMapCoordinates(e.pos())
        crs_map = self.canvas.mapSettings().destinationCrs()
        transform = QgsCoordinateTransform(crs_map, self.crs_wgs84, QgsProject.instance())
        point_wgs84 = transform.transform(point_map)

        QgsMessageLog.logMessage(f'Clique em WGS84: Lat={point_wgs84.y():.6f}, Lon={point_wgs84.x():.6f}', 'NdviSatveg Plugin', Qgis.Info)
        
        self.plugin_action.draw_pixel_square(point_wgs84)
        self.plugin_action.get_ndvi_data(point_wgs84.y(), point_wgs84.x())

    def activate(self):
        self.canvas.setCursor(Qt.CrossCursor)
        super().activate()

    def deactivate(self):
        self.plugin_action.clear_pixel_square()
        super().deactivate()

class NdviSatveg:
    MUNICIPIOS_GPKG_FILENAME = "BR_Municipios_2021.gpkg"
    MUNICIPIOS_FIELD_NAME = 'NM_MUN'
    MUNICIPIOS_FIELD_UF = 'SIGLA'

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.translator = None
        self.actions = []
        self.pixel_square_rb = None
        self.municipios_layer = None
        self.map_tool = None
        self.action_button = None
        self.ndvi_dock_widget = None
        self.plot_canvas = None
        self.current_fig = None
        self.hover_connection_id = None

        self.load_locale()
        self.menu_name = u'&NDVI-SATVeg'
        self.menu = self.tr(self.menu_name)
        self.toolbar_name = u'NdviSatvegToolbar'
        self.toolbar = self.iface.addToolBar(self.tr('NDVI-SATVeg Toolbar Title'))
        self.toolbar.setObjectName(self.toolbar_name)

    def load_locale(self):
        locale_name = QSettings().value('locale/userLocale', QLocale.system().name())
        locale_code = locale_name[0:2]
        locale_path = os.path.join(self.plugin_dir, 'i18n', f'NdviSatveg_{locale_code}.qm')
        if os.path.exists(locale_path):
            self.translator = QTranslator()
            if self.translator.load(locale_path):
                QCoreApplication.installTranslator(self.translator)

    def tr(self, message):
        return QCoreApplication.translate('NdviSatveg', message)

    def add_action(self, icon_path, text, callback, checkable=False, parent=None, status_tip=None):
        action = QAction(QIcon(icon_path), text, parent)
        action.triggered.connect(callback)
        action.setCheckable(checkable)
        if status_tip: action.setStatusTip(status_tip)
        self.toolbar.addAction(action)
        self.iface.addPluginToMenu(self.menu, action)
        self.actions.append(action)
        return action

    def initGui(self):
        icon_path = ':/plugins/NDVI_DATVeg/icon.png'
        self.action_button = self.add_action(
            icon_path, self.tr(u'Obter Curva NDVI Interativa (Clique no Mapa)'),
            self.run, True, self.iface.mainWindow(),
            self.tr("Ativa/Desativa ferramenta para obter curva NDVI clicando no mapa"))
        self.action_button.setShortcut('n')
        self.map_tool = PointTool(self.iface.mapCanvas(), self)
        self.iface.mapCanvas().mapToolSet.connect(self.handle_map_tool_change)

    def unload(self):
        self.clear_pixel_square()
        self.municipios_layer = None
        if self.ndvi_dock_widget:
            self.iface.removeDockWidget(self.ndvi_dock_widget)
            self.ndvi_dock_widget.deleteLater()
            self.ndvi_dock_widget = None
        if self.current_fig:
            plt.close(self.current_fig)
            self.current_fig = None
        try:
            self.iface.mapCanvas().mapToolSet.disconnect(self.handle_map_tool_change)
        except (TypeError, RuntimeError): pass
        for action in self.actions:
            self.iface.removePluginMenu(self.tr(self.menu_name), action)
            self.toolbar.removeAction(action)
        del self.toolbar
        del self.map_tool

    def handle_map_tool_change(self, new_tool: QgsMapTool):
        if new_tool != self.map_tool and self.action_button and self.action_button.isChecked():
            self.action_button.setChecked(False)

    def run(self):
        if self.action_button and self.action_button.isChecked():
            self.iface.mapCanvas().setMapTool(self.map_tool)
        else:
            if self.iface.mapCanvas().mapTool() == self.map_tool:
                self.iface.mapCanvas().unsetMapTool(self.map_tool)
    
    def clear_pixel_square(self):
        if self.pixel_square_rb:
            self.pixel_square_rb.reset()
            self.pixel_square_rb = None
        if self.iface.mapCanvas():
            self.iface.mapCanvas().refresh()

    def draw_pixel_square(self, point_wgs84: QgsPointXY):
        self.clear_pixel_square() 
        origin_lon, origin_lat = -81.49999999999997, 12.999999989999996
        pixel_width, pixel_height = 0.002083333333333, -0.002083333333333
        col = math.floor((point_wgs84.x() - origin_lon) / pixel_width)
        row = math.floor((point_wgs84.y() - origin_lat) / pixel_height)
        min_lon = origin_lon + col * pixel_width
        max_lat = origin_lat + row * pixel_height
        pixel_geom = QgsGeometry.fromWkt(f'POLYGON(({min_lon} {max_lat + pixel_height}, {min_lon + pixel_width} {max_lat + pixel_height}, {min_lon + pixel_width} {max_lat}, {min_lon} {max_lat}, {min_lon} {max_lat + pixel_height}))')
        transform_to_map = QgsCoordinateTransform(QgsCoordinateReferenceSystem("EPSG:4326"), self.iface.mapCanvas().mapSettings().destinationCrs(), QgsProject.instance())
        pixel_geom.transform(transform_to_map)
        self.pixel_square_rb = QgsRubberBand(self.iface.mapCanvas())
        self.pixel_square_rb.setToGeometry(pixel_geom)
        self.pixel_square_rb.setColor(QColor(255, 170, 0, 255))
        self.pixel_square_rb.setWidth(2)
        self.pixel_square_rb.setFillColor(QColor(255, 170, 0, 50))
        self.pixel_square_rb.show()

    def _get_municipio_name(self, lat, lon):
        try:
            if not self.municipios_layer or not self.municipios_layer.isValid():
                gpkg_path = os.path.join(self.plugin_dir, 'Satveg', self.MUNICIPIOS_GPKG_FILENAME)
                if not os.path.exists(gpkg_path): return self.tr("Arquivo de municípios não encontrado")
                self.municipios_layer = QgsVectorLayer(gpkg_path, "municipios_memoria", "ogr")
                if not self.municipios_layer.isValid(): return self.tr("Erro ao carregar camada de municípios")
            point_geom = QgsGeometry.fromPointXY(QgsPointXY(lon, lat))
            transform = QgsCoordinateTransform(QgsCoordinateReferenceSystem("EPSG:4326"), self.municipios_layer.crs(), QgsProject.instance())
            point_geom.transform(transform)
            request = QgsFeatureRequest().setFilterRect(point_geom.boundingBox()).setFlags(QgsFeatureRequest.ExactIntersect)
            for feature in self.municipios_layer.getFeatures(request):
                return f"{feature[self.MUNICIPIOS_FIELD_NAME]} - {feature[self.MUNICIPIOS_FIELD_UF]}"
            return self.tr("Não localizado (fora da área)")
        except Exception as e:
            QgsMessageLog.logMessage(f"Erro na busca de município: {e}", "NdviSatveg Plugin", Qgis.Critical)
            return self.tr("Erro na busca local")

    def get_ndvi_data(self, lat, lon):
        municipio_name = self._get_municipio_name(lat, lon)
        try:
            all_data = satveg_core.get_timeseries(lat, lon)
            if not all_data or "date" not in all_data or "ndvi" not in all_data or not all_data["date"] or not all_data["ndvi"]:
                self.iface.messageBar().pushMessage(self.tr("Aviso SATVeg"), self.tr("Não foi possível extrair dados válidos."), level=Qgis.Warning, duration=10)
                return
            self.show_ndvi_plot(all_data["date"], all_data["ndvi"], lat, lon, municipio_name)
        except Exception as e:
            QgsMessageLog.logMessage(f'Erro SATVeg: {e}', 'NdviSatveg Plugin', Qgis.Critical)
            self.iface.messageBar().pushMessage(self.tr("Erro Operação SATVeg"), f"Falha: {e}", level=Qgis.Critical, duration=10)

    def _apply_plot_aesthetics(self, ax):
        veg_ranges = {
            'low':    {'min': 0.0, 'max': 0.25, 'color': '#FFC0CB'},
            'medium': {'min': 0.25, 'max': 0.5, 'color': '#FFFFE0'},
            'high':   {'min': 0.5, 'max': 0.75, 'color': '#90EE90'},
            'vhigh':  {'min': 0.75, 'max': 1.0, 'color': '#3CB371'}
        }
        for _, v_range in veg_ranges.items():
            ax.axhspan(v_range['min'], v_range['max'], facecolor=v_range['color'], alpha=0.35, zorder=0)
        ax.set_ylabel("NDVI", fontsize=12)
        ax.grid(True, linestyle='-', linewidth=0.75, color='lightgray', zorder=1)

    def _format_plot_xaxis(self, ax, dates):
        if not dates: return
        span_days = (max(dates) - min(dates)).days
        if span_days > 1825: locator, fmt = mdates.YearLocator(), mdates.DateFormatter('%Y')
        elif span_days > 730: locator, fmt = mdates.MonthLocator(interval=6), mdates.DateFormatter('%b %Y')
        elif span_days > 180: locator, fmt = mdates.MonthLocator(interval=2), mdates.DateFormatter('%b %Y')
        else: locator, fmt = mdates.AutoDateLocator(), mdates.DateFormatter('%d-%b')
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(fmt)
        ax.get_figure().autofmt_xdate(rotation=30, ha='right')

    def _handle_plot_widget_closed(self):
        if self.current_fig and self.hover_connection_id:
            try: self.current_fig.canvas.mpl_disconnect(self.hover_connection_id)
            except: pass
        self.hover_connection_id = None
        self.ndvi_dock_widget = None
        self.plot_canvas = None
        self.current_fig = None
    
    def _create_plot_dock_widget(self):
        if self.ndvi_dock_widget is None:
            self.ndvi_dock_widget = NdviSatvegDockWidget(self.iface.mainWindow())
            self.ndvi_dock_widget.setObjectName("NdviSatvegPlotDockWidget")
            if self.ndvi_dock_widget.label:
                self.ndvi_dock_widget.label.deleteLater()
                self.ndvi_dock_widget.label = None
            self.current_fig = plt.figure(figsize=(8, 2.25))
            self.plot_canvas = FigureCanvas(self.current_fig)
            self.ndvi_dock_widget.gridLayout.addWidget(self.plot_canvas, 0, 0)
            self.ndvi_dock_widget.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.TopDockWidgetArea | Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
            self.ndvi_dock_widget.closingPlugin.connect(self._handle_plot_widget_closed)
            self.iface.addDockWidget(Qt.BottomDockWidgetArea, self.ndvi_dock_widget)
        self.ndvi_dock_widget.show()
        self.ndvi_dock_widget.raise_()

    def show_ndvi_plot(self, all_dates_py, all_ndvi_values, lat, lon, municipio_name="N/A"):
        try:
            self._create_plot_dock_widget()

            if self.hover_connection_id and self.current_fig.canvas:
                try: self.current_fig.canvas.mpl_disconnect(self.hover_connection_id)
                except: pass
            
            self.current_fig.clf()
            ax_main = self.current_fig.add_subplot(111)
            fig = self.current_fig
            
            if not all_dates_py:
                ax_main.text(0.5, 0.5, self.tr("Sem dados disponíveis."), ha='center', va='center')
                self.plot_canvas.draw()
                return

            self._apply_plot_aesthetics(ax_main)
            
            line, = ax_main.plot(all_dates_py, all_ndvi_values, color='#38A800', linestyle='-', linewidth=2, picker=5)
            self._format_plot_xaxis(ax_main, all_dates_py)
            
            min_y = min(all_ndvi_values) if all_ndvi_values else 0
            ax_main.set_ylim(min(-0.05, min_y - 0.05), 1.05)
            ax_main.margins(x=0.01)

            annot = ax_main.annotate("", xy=(0,0), xytext=(20,20), textcoords="offset points",
                                     bbox=dict(boxstyle="round,pad=0.5", fc="ivory", ec="#2E8B57", lw=1),
                                     arrowprops=dict(arrowstyle="->", connectionstyle="arc3,rad=0.1", ec="#2E8B57"), zorder=10)
            annot.set_visible(False)

            def update_annot(ind):
                pos = line.get_data()
                point_index = ind["ind"][0]
                date_obj = pos[0][point_index]
                y_point = pos[1][point_index]
                
                # CORREÇÃO: Converte a data para a representação numérica do Matplotlib ANTES de usá-la
                x_point_num = mdates.date2num(date_obj)
                annot.xy = (x_point_num, y_point)

                date_str = date_obj.strftime('%d/%m/%Y')
                text = f"Data: {date_str}\nNDVI: {y_point:.4f}"
                annot.set_text(text)
                annot.get_bbox_patch().set_alpha(0.9)
                
                xlim = ax_main.get_xlim()
                ylim = ax_main.get_ylim()
                
                x_is_right = x_point_num > (xlim[0] + xlim[1]) / 2.0
                y_is_top = y_point > (ylim[0] + ylim[1]) / 2.0
                
                offset = 20
                x_offset = -offset if x_is_right else offset
                y_offset = -offset if y_is_top else offset
                
                annot.set_horizontalalignment('right' if x_is_right else 'left')
                annot.set_verticalalignment('top' if y_is_top else 'bottom')
                annot.set_position((x_offset, y_offset))

            def on_hover(event):
                vis = annot.get_visible()
                if event.inaxes != ax_main:
                    if vis:
                        annot.set_visible(False)
                        fig.canvas.draw_idle()
                    return

                contains_mouse, ind = line.contains(event)
                if contains_mouse:
                    update_annot(ind)
                    annot.set_visible(True)
                    fig.canvas.draw_idle()
                elif vis:
                    annot.set_visible(False)
                    fig.canvas.draw_idle()

            self.hover_connection_id = self.current_fig.canvas.mpl_connect('motion_notify_event', on_hover)

            dock_title = self.tr("Curva NDVI Interativa") + f" - Lat: {lat:.3f}, Lon: {lon:.3f} - {municipio_name}"
            self.ndvi_dock_widget.setWindowTitle(dock_title)
            
            self.current_fig.tight_layout(pad=0.5)
            self.plot_canvas.draw()

        except Exception as e:
            QgsMessageLog.logMessage(f'Erro ao criar gráfico: {e}', 'NdviSatveg Plugin', Qgis.Critical)
            self.iface.messageBar().pushMessage(self.tr("Erro no Gráfico"), f"Falha: {e}", level=Qgis.Critical, duration=7)