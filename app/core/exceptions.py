class EcoFlowError(Exception): pass
class ExtractionError(EcoFlowError): pass
class ToolError(EcoFlowError): pass
class ConnectorError(EcoFlowError): pass
class IdempotencyError(EcoFlowError): pass
