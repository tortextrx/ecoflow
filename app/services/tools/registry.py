from .entidades_tools import CrearEntidadTool, ObtenerEntidadTool, ListarEntidadesTool
from .facturacion_tools import GrabarFacturacionTool, ObtenerFacturacionTool, ListarFacturacionesTool, BorrarFacturacionTool
from .servicios_tools import CrearServicioTool, ObtenerServicioTool, BorrarServicioTool, GrabarHistoricoTool, ObtenerHistoricoServicioTool
from .articulos_tools import CrearArticuloTool, ObtenerArticuloTool, ListarArticulosTool
from .contratos_tools import CrearContratoTool, ObtenerContratoTool, ListarContratosTool, ModificarContratoTool, BorrarContratoTool
from .extraer_documento import ExtractorMultimodalTool
from .buscar_entidad import BuscarEntidadTool
from .registrar_gasto import RegistrarGastoTool

class ToolRegistry:
    def __init__(self):
        # Entidades
        self.crear_entidad = CrearEntidadTool()
        self.obtener_entidad = ObtenerEntidadTool()
        self.listar_entidades = ListarEntidadesTool()
        self.buscar_entidad = BuscarEntidadTool()
        
        # Facturacion
        self.grabar_facturacion = GrabarFacturacionTool()
        self.obtener_facturacion = ObtenerFacturacionTool()
        self.listar_facturaciones = ListarFacturacionesTool()
        self.borrar_facturacion = BorrarFacturacionTool()
        self.registrar_gasto = RegistrarGastoTool()
        
        # Articulos
        self.crear_articulo = CrearArticuloTool()
        self.obtener_articulo = ObtenerArticuloTool()
        self.listar_articulos = ListarArticulosTool()
        
        # Servicios
        self.crear_servicio = CrearServicioTool()
        self.obtener_servicio = ObtenerServicioTool()
        self.borrar_servicio = BorrarServicioTool()
        self.grabar_historico = GrabarHistoricoTool()
        self.obtener_historico_servicio = ObtenerHistoricoServicioTool()
        
        # Contratos (nuevo)
        self.crear_contrato = CrearContratoTool()
        self.obtener_contrato = ObtenerContratoTool()
        self.listar_contratos = ListarContratosTool()
        self.modificar_contrato = ModificarContratoTool()
        self.borrar_contrato = BorrarContratoTool()
        
        # Otros
        self.extractor = ExtractorMultimodalTool()

tool_registry = ToolRegistry()
